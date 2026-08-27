import urllib.request, json

# Login as admin
req = urllib.request.Request('http://127.0.0.1:8000/api/auth/login', data=json.dumps({'username': 'admin@nckh.vn', 'password': 'nckh2025'}).encode('utf-8'), headers={'Content-Type': 'application/json'})
res = json.loads(urllib.request.urlopen(req).read())
token = res['token']

# Create a test user
user_data = {
    "email": "testuser@nckh.vn",
    "password": "userpass",
    "name": "Test User",
    "role": "Khachhang",
    "status": "Đang hoạt động",
    "assignedCameras": [],
    "phone": "0912345678"
}
try:
    req_create = urllib.request.Request('http://127.0.0.1:8000/api/users', data=json.dumps(user_data).encode('utf-8'), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'})
    print("CREATE response:", urllib.request.urlopen(req_create).read().decode('utf-8'))
except Exception as e:
    print(e)

# Login as test user
req_user = urllib.request.Request('http://127.0.0.1:8000/api/auth/login', data=json.dumps({'username': 'testuser@nckh.vn', 'password': 'userpass'}).encode('utf-8'), headers={'Content-Type': 'application/json'})
res_user = json.loads(urllib.request.urlopen(req_user).read())
token_user = res_user['token']

# User tries to update their own profile
put_data = {
    "email": "testuser@nckh.vn",
    "name": "Test User Updated",
    "role": "Khachhang",
    "status": "Đang hoạt động",
    "assignedCameras": [],
    "phone": "0999999999"
}
try:
    req_put = urllib.request.Request('http://127.0.0.1:8000/api/users/testuser@nckh.vn', data=json.dumps(put_data).encode('utf-8'), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token_user}'}, method='PUT')
    print("PUT response:", urllib.request.urlopen(req_put).read().decode('utf-8'))
except Exception as e:
    print("PUT Error:", e)
