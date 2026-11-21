"""
File: src/core/protobuf_patch.py
Chức năng chính: Tự động vá tương thích (Compatibility Monkey Patch) giữa Google Protobuf >= 5.x và MediaPipe 0.10.x.

Nguyên nhân lỗi gốc:
1. AttributeError: 'MessageFactory' object has no attribute 'GetPrototype':
   Trong Protobuf 5+, phương thức GetPrototype đã được đổi tên thành GetMessageClass.
2. AttributeError: 'google._upb._message.FieldDescriptor' object has no attribute 'label':
   Trong Protobuf 5+, backend C++/UPB đã loại bỏ thuộc tính .label và thay bằng .is_repeated, .is_required.
   MediaPipe 0.10.14 lại truy cập trực tiếp vào .label gây crash khi khởi động Pose.

Module này tự động vá tương thích ngay khi được nạp, giúp hệ thống chạy trơn tru với mọi phiên bản Protobuf mới nhất.
"""

from __future__ import annotations


def apply_protobuf_patch() -> None:
    # 1. Patch MessageFactory.GetPrototype cho Protobuf 5+
    try:
        from google.protobuf import message_factory
        if not hasattr(message_factory.MessageFactory, "GetPrototype"):
            message_factory.MessageFactory.GetPrototype = staticmethod(message_factory.GetMessageClass)
        if not hasattr(message_factory.MessageFactory, "GetMessages"):
            message_factory.MessageFactory.GetMessages = staticmethod(message_factory.GetMessages)
    except Exception:
        pass

    # 2. Patch solution_base._modify_calculator_options cho FieldDescriptor.label trong Protobuf 5+
    try:
        import mediapipe.python.solution_base as solution_base
        from collections.abc import Iterable
        from google.protobuf import descriptor

        if getattr(solution_base.SolutionBase, "_protobuf_patched", False):
            return

        def generate_nested_calculator_params(flat_map):
            nested_map = {}
            for compound_name, field_value in flat_map.items():
                calculator_and_field_name = compound_name.split('.')
                if len(calculator_and_field_name) != 2:
                    raise ValueError(f'The key "{compound_name}" in the calculator_params is invalid.')
                calculator_name = calculator_and_field_name[0]
                field_name = calculator_and_field_name[1]
                if calculator_name in nested_map:
                    nested_map[calculator_name].append((field_name, field_value))
                else:
                    nested_map[calculator_name] = [(field_name, field_value)]
            return nested_map

        def modify_options_fields(calculator_options, options_field_list):
            for field_name, field_value in options_field_list:
                if field_value is None:
                    calculator_options.ClearField(field_name)
                else:
                    field_desc = calculator_options.DESCRIPTOR.fields_by_name[field_name]
                    is_repeated = getattr(field_desc, 'is_repeated', False)
                    if not is_repeated and hasattr(field_desc, 'label'):
                        is_repeated = (field_desc.label == descriptor.FieldDescriptor.LABEL_REPEATED)
                    if is_repeated:
                        if not isinstance(field_value, Iterable):
                            raise ValueError(
                                f'{field_name} is a repeated proto field but the value '
                                f'to be set is {type(field_value)}, which is not iterable.'
                            )
                        calculator_options.ClearField(field_name)
                        for elem in field_value:
                            getattr(calculator_options, field_name).append(elem)
                    else:
                        setattr(calculator_options, field_name, field_value)

        def patched_modify_calculator_options(self, calculator_graph_config, calculator_params):
            nested_params = generate_nested_calculator_params(calculator_params)
            for node in calculator_graph_config.node:
                if node.calculator in nested_params:
                    node_options = node.options
                    for extension_handle in list(node_options.Extensions):
                        modify_options_fields(node_options.Extensions[extension_handle], nested_params[node.calculator])

        solution_base.SolutionBase._modify_calculator_options = patched_modify_calculator_options
        solution_base.SolutionBase._protobuf_patched = True
    except Exception:
        pass


apply_protobuf_patch()
