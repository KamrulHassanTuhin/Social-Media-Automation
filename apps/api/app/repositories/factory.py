from app.config.settings import get_settings
from app.repositories.content import InMemoryContentRepository


def build_content_repository():
    settings = get_settings()
    if settings.app_env != "local" and not (settings.supabase_url and settings.supabase_service_role_key):
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required outside local mode.")
    if settings.supabase_url and settings.supabase_service_role_key and settings.app_env != "local":
        from app.repositories.supabase_content import SupabaseContentRepository

        return SupabaseContentRepository(settings.supabase_url, settings.supabase_service_role_key)
    return InMemoryContentRepository()


content_repository = build_content_repository()
