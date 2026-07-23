from app.config.settings import get_settings
from app.repositories.membership import InMemoryMembershipRepository


def build_membership_repository():
    settings = get_settings()
    if settings.app_env == "local":
        return InMemoryMembershipRepository()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required outside local mode.")
    from app.repositories.membership import SupabaseMembershipRepository

    return SupabaseMembershipRepository(settings.supabase_url, settings.supabase_service_role_key)


membership_repository = build_membership_repository()
