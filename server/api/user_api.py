from fastapi import APIRouter, Depends
from server.models.request import LoginRequest, RegisterRequest
from server.service.user_server import UserService
from server.utils.auth import get_current_user
from server.models.request import UpdateUserInfoRequest, UpdatePasswordRequest

router = APIRouter(prefix="/user", tags=["user"])
service = UserService()


@router.post("/register")
def register(req: RegisterRequest):
    return service.register(req.username, req.password, req.email, req.phone)


@router.post("/login")
def login(req: LoginRequest):
    return service.login(req.username, req.password)

@router.get("/me")
def get_user_info(user:dict = Depends(get_current_user)):
    return service.get_user_by_id(user["id"])
    
@router.put("/profile")
def update_profile(req: UpdateUserInfoRequest, user: dict = Depends(get_current_user)):
    """修改个人信息"""
    return service.update_profile(user["id"], req)

@router.put("/password")
def update_password(req: UpdatePasswordRequest, user: dict = Depends(get_current_user)):
    """修改密码"""
    return service.update_password(user["id"], req.old_password, req.new_password)