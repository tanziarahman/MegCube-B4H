# Entry point kept at the project root so `uvicorn main:app --reload` still works.
from app.main import app  # noqa: F401
