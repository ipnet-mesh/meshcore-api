"""FastAPI dependency injection for database and MeshCore access."""

from typing import Generator, Optional
from fastapi import Depends
from sqlalchemy.orm import Session

from ..database.engine import session_scope
from ..meshcore.interface import MeshCoreInterface


# Global MeshCore instance (set during app startup)
_meshcore_instance: Optional[MeshCoreInterface] = None


def set_meshcore_instance(meshcore: MeshCoreInterface) -> None:
    """
    Set the global MeshCore instance.

    This is called during application startup to make the MeshCore
    instance available to all API routes.

    Args:
        meshcore: The MeshCore interface instance
    """
    global _meshcore_instance
    _meshcore_instance = meshcore


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.

    Yields:
        SQLAlchemy session

    Example:
        ```python
        @router.get("/nodes")
        def list_nodes(db: Session = Depends(get_db)):
            return db.query(Node).all()
        ```
    """
    with session_scope() as session:
        yield session


def get_meshcore() -> MeshCoreInterface:
    """
    Dependency to get the MeshCore instance.

    Returns:
        MeshCore interface instance

    Raises:
        RuntimeError: If MeshCore instance has not been set

    Example:
        ```python
        @router.post("/commands/ping")
        def ping_node(meshcore: MeshCoreInterface = Depends(get_meshcore)):
            meshcore.ping(destination)
        ```
    """
    if _meshcore_instance is None:
        raise RuntimeError("MeshCore instance not initialized")
    return _meshcore_instance
