from app.config.settings import get_settings
from app.repositories.workspace import InMemoryWorkspaceRepository


def build_workspace_repository():
    settings = get_settings()
    if settings.app_env != "local" and not (settings.supabase_url and settings.supabase_service_role_key):
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required outside local mode.")
    if settings.supabase_url and settings.supabase_service_role_key and settings.app_env != "local":
        from app.repositories.workspace import SupabaseWorkspaceRepository

        return SupabaseWorkspaceRepository(settings.supabase_url, settings.supabase_service_role_key)
    return InMemoryWorkspaceRepository()


workspace_repository = build_workspace_repository()
