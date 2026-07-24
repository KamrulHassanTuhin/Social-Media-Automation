-- Restrict worker-only RPCs to the backend service role.
-- These functions mutate queue state and must never be callable by public clients.

revoke execute on function public.claim_next_job(text, integer) from public, anon, authenticated;
grant execute on function public.claim_next_job(text, integer) to service_role;

revoke execute on function public.claim_next_notification(text, integer) from public, anon, authenticated;
grant execute on function public.claim_next_notification(text, integer) to service_role;

revoke execute on function public.complete_job(uuid) from public, anon, authenticated;
grant execute on function public.complete_job(uuid) to service_role;

-- Credential ciphertext is backend-only; keep it inaccessible to browser roles.
revoke all on public.integration_credentials from anon, authenticated;
