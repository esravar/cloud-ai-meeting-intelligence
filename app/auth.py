import uuid

from app.models import User
from app.repository import UserRepository
from app.schemas import TokenResponse, UserResponse
from app.security import AuthenticationError, PasswordService, TokenService


class UserAlreadyExistsError(RuntimeError):
    pass


class AuthService:
    def __init__(
        self,
        repository: UserRepository,
        passwords: PasswordService,
        tokens: TokenService,
    ):
        self._repository = repository
        self._passwords = passwords
        self._tokens = tokens

    def register(self, email: str, password: str) -> UserResponse:
        if self._repository.get_by_email(email):
            raise UserAlreadyExistsError("A user with this email already exists.")
        user = self._repository.create(email, self._passwords.hash(password))
        return self.response(user)

    def login(self, email: str, password: str) -> TokenResponse:
        user = self._repository.get_by_email(email)
        if not user or not self._passwords.verify(password, user.password_hash):
            raise AuthenticationError("Incorrect email or password.")
        return TokenResponse(access_token=self._tokens.create(user.id))

    def current_user(self, user_id: uuid.UUID) -> User:
        user = self._repository.get(user_id)
        if not user:
            raise AuthenticationError("Authenticated user no longer exists.")
        return user

    @staticmethod
    def response(user: User) -> UserResponse:
        return UserResponse(id=user.id, email=user.email, created_at=user.created_at)
