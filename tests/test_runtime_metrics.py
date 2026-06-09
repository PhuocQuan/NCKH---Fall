from src.runtime_metrics import FPSCounter


def test_fps_counter_returns_zero_until_two_frames():
    counter = FPSCounter()

    assert counter.fps == 0.0
    counter._timestamps.append(1.0)

    assert counter.fps == 0.0


def test_fps_counter_uses_window_elapsed_time():
    counter = FPSCounter(window_size=3)
    counter._timestamps.extend([1.0, 1.5, 2.0])

    assert counter.fps == 2.0
