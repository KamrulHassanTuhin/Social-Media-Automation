from dataclasses import dataclass


@dataclass(frozen=True)
class InvitationEmail:
    subject: str
    preview: str
    body_text: str


def build_invitation_email(email: str, workspace_name: str, inviter_name: str, accept_url: str) -> InvitationEmail:
    return InvitationEmail(
        subject=f"You have been invited to {workspace_name} on Nova Studio",
        preview=f"{inviter_name} invited {email} to collaborate in {workspace_name}.",
        body_text=(f"Hi,\n\n{inviter_name} invited you to join {workspace_name} on Nova Studio. "
                   f"Accept the invitation here: {accept_url}\n\n"
                   "Your access will be limited by the workspace role assigned by an admin.\n\nContent Studio"),
    )
