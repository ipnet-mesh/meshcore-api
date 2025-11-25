"""FastAPI dependency injection for database and MeshCore access."""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database.engine import session_scope
from ..meshcore.interface import MeshCoreInterface
from ..config import Config


# Global MeshCore instance (set during app startup)
_meshcore_instance: Optional[MeshCoreInterface] = None

# Global Config instance (set during app startup)
_config_instance: Optional[Config] = None


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


def set_config_instance(config: Config) -> None:
    """
    Set the global Config instance.

    This is called during application startup to make the Config
    instance available to all API routes.

    Args:
        config: The Config instance
    """
    global _config_instance
    _config_instance = config


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


def check_write_enabled() -> None:
    """
    Dependency to check if write operations are enabled.

    Raises:
        HTTPException: If write operations are disabled (read-only mode)

    Example:
        ```python
        @router.post("/commands/ping", dependencies=[Depends(check_write_enabled)])
        def ping_node(meshcore: MeshCoreInterface = Depends(get_meshcore)):
            meshcore.ping(destination)
        ```
    """
    if _config_instance is None:
        raise RuntimeError("Config instance not initialized")

    if not _config_instance.enable_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Writing and specific actions not available in read-only mode"
        )
