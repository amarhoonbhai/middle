import logging
import asyncio
from typing import List, Tuple, Union, Any, Optional
from telethon import TelegramClient, utils
from telethon.tl import types
from telethon.tl.functions.messages import CreateChatRequest, AddChatUserRequest, EditChatTitleRequest, DeleteChatUserRequest
from telethon.tl.functions.channels import EditTitleRequest, LeaveChannelRequest
from telethon.errors import (
    UserPrivacyRestrictedError,
    UserAlreadyParticipantError,
    FloodWaitError,
    RPCError
)

logger = logging.getLogger(__name__)

async def call_with_retry(client: TelegramClient, request: Any) -> Any:
    """
    Executes a Telethon RPC request.
    If a FloodWaitError (rate limit) is encountered, automatically sleeps for 
    the required duration before retrying the call once.
    """
    try:
        return await client(request)
    except FloodWaitError as e:
        logger.warning(f"Telegram FloodWaitError (Rate Limit) hit. Sleeping for {e.seconds} seconds before retrying...")
        await asyncio.sleep(e.seconds)
        # Retry after sleep
        return await client(request)

async def resolve_user_entity(client: TelegramClient, user_str: Union[str, int]) -> Any:
    """
    Resolves a username, phone, or user ID to a Telegram InputUser/Entity.
    Throws ValueError or UsernameNotOccupiedError if resolution fails.
    """
    if isinstance(user_str, str):
        user_str = user_str.strip()
        # If it looks like a numeric ID, cast to int
        if user_str.isdigit():
            user_str = int(user_str)
        elif user_str.startswith("-") and user_str[1:].isdigit():
            user_str = int(user_str)
            
    return await client.get_entity(user_str)

def _extract_chat_entity(result: Any) -> Any:
    """Helper to extract the created chat entity from CreateChatRequest result."""
    if hasattr(result, "updates"):
        return result.updates.chats[0]
    elif hasattr(result, "chats"):
        return result.chats[0]
    else:
        raise AttributeError(f"Could not find created chat in Telegram response: {type(result)}")

async def create_mm_group(
    client: TelegramClient,
    title: str,
    participants: List[Union[str, int]]
) -> Tuple[Any, List[str], List[str]]:
    """
    Creates a new legacy group chat with the given title.
    Attempts to add both participants, falling back gracefully to adding them
    singly if a privacy restriction or error is hit.
    
    Returns:
        Tuple of (chat_entity, list_of_added_identifiers, list_of_failed_identifiers)
    """
    resolved_users = []
    failed_resolutions = []
    
    for p in participants:
        try:
            user_ent = await resolve_user_entity(client, p)
            resolved_users.append(user_ent)
        except Exception as e:
            logger.error(f"Failed to resolve participant '{p}': {e}")
            failed_resolutions.append(str(p))
            
    if not resolved_users:
        raise ValueError(f"Could not resolve any of the participants: {participants}")
        
    chat_entity = None
    added_users: List[str] = []
    failed_users: List[str] = []
    
    # Attempt to create group with all resolved users at once
    try:
        result = await call_with_retry(client, CreateChatRequest(
            users=resolved_users,
            title=title
        ))
        chat_entity = _extract_chat_entity(result)
        # Successfully created with all users
        for u in resolved_users:
            identifier = getattr(u, 'username', None) or str(u.id)
            added_users.append(f"@{identifier}" if getattr(u, 'username', None) else identifier)
    except (UserPrivacyRestrictedError, RPCError) as e:
        logger.warning(f"Could not create group with all participants at once: {e}. Trying fallbacks.")
        
        # Fallback: Create group with first resolved user, then invite others
        for idx, primary_user in enumerate(resolved_users):
            try:
                result = await call_with_retry(client, CreateChatRequest(
                    users=[primary_user],
                    title=title
                ))
                chat_entity = _extract_chat_entity(result)
                primary_id = getattr(primary_user, 'username', None) or str(primary_user.id)
                added_users.append(f"@{primary_id}" if getattr(primary_user, 'username', None) else primary_id)
                
                # Try adding the rest of the users
                remaining_users = resolved_users[idx+1:] + resolved_users[:idx]
                for other_user in remaining_users:
                    try:
                        await call_with_retry(client, AddChatUserRequest(
                            chat_id=chat_entity.id,
                            user_id=other_user,
                            fwd_limit=0
                        ))
                        other_id = getattr(other_user, 'username', None) or str(other_user.id)
                        added_users.append(f"@{other_id}" if getattr(other_user, 'username', None) else other_id)
                    except (UserPrivacyRestrictedError, UserAlreadyParticipantError) as ae:
                        logger.warning(f"Failed to add participant {other_user.id}: {ae}")
                        other_id = getattr(other_user, 'username', None) or str(other_user.id)
                        failed_users.append(f"@{other_id}" if getattr(other_user, 'username', None) else other_id)
                    except Exception as ae:
                        logger.error(f"Unexpected error adding participant {other_user.id}: {ae}")
                        other_id = getattr(other_user, 'username', None) or str(other_user.id)
                        failed_users.append(f"@{other_id}" if getattr(other_user, 'username', None) else other_id)
                break
            except Exception as ce:
                logger.warning(f"Failed to create group with user {primary_user.id} as primary: {ce}")
                continue
                
    if not chat_entity:
        logger.info("Could not create legacy group due to privacy settings. Falling back to Megagroup (Supergroup) creation...")
        try:
            from telethon.tl.functions.channels import CreateChannelRequest
            result = await call_with_retry(client, CreateChannelRequest(
                title=title,
                about="Middleman Escrow Group",
                megagroup=True
            ))
            chat_entity = _extract_chat_entity(result)
            # Since we couldn't add them directly, add all resolved users to failed list
            for u in resolved_users:
                identifier = getattr(u, 'username', None) or str(u.id)
                failed_users.append(f"@{identifier}" if getattr(u, 'username', None) else identifier)
        except Exception as e:
            logger.error(f"Failed to create megagroup fallback: {e}")
            raise RuntimeError(f"Failed to create group: privacy restrictions on all participants or other Telegram API limits. Fallback megagroup creation also failed: {e}")
        
    failed_users.extend(failed_resolutions)
    return chat_entity, added_users, failed_users

async def rename_group(client: TelegramClient, chat_entity: Any, new_title: str) -> None:
    """Renames the title of a legacy group or supergroup/channel."""
    peer = await client.get_input_entity(chat_entity)
    if isinstance(peer, types.InputPeerChannel):
        await call_with_retry(client, EditTitleRequest(channel=peer, title=new_title))
    elif isinstance(peer, types.InputPeerChat):
        await call_with_retry(client, EditChatTitleRequest(chat_id=peer.chat_id, title=new_title))
    else:
        # Fallback to signed ID checks
        chat_id = utils.get_peer_id(chat_entity)
        if str(chat_id).startswith("-100"):
            await call_with_retry(client, EditTitleRequest(channel=chat_entity, title=new_title))
        else:
            await call_with_retry(client, EditChatTitleRequest(chat_id=abs(chat_id), title=new_title))

async def leave_group(client: TelegramClient, chat_entity: Any) -> None:
    """Leaves a group chat or supergroup/channel."""
    peer = await client.get_input_entity(chat_entity)
    if isinstance(peer, types.InputPeerChannel):
        await call_with_retry(client, LeaveChannelRequest(channel=peer))
    elif isinstance(peer, types.InputPeerChat):
        await call_with_retry(client, DeleteChatUserRequest(chat_id=peer.chat_id, user_id='me'))
    else:
        chat_id = utils.get_peer_id(chat_entity)
        if str(chat_id).startswith("-100"):
            await call_with_retry(client, LeaveChannelRequest(channel=chat_entity))
        else:
            await call_with_retry(client, DeleteChatUserRequest(chat_id=abs(chat_id), user_id='me'))

async def get_invite_link(client: TelegramClient, chat_entity: Any) -> Optional[str]:
    """Generates and returns an invite link for a legacy group or channel."""
    from telethon.tl.functions.messages import ExportChatInviteRequest
    try:
        # Retrieve the peer ID from the entity safely
        chat_id = utils.get_peer_id(chat_entity)
        
        # Check if this represents a supergroup / channel
        is_channel = False
        if isinstance(chat_entity, (types.InputPeerChannel, types.PeerChannel, types.Channel)):
            is_channel = True
        elif isinstance(chat_id, int) and str(chat_id).startswith("-100"):
            is_channel = True
            
        if is_channel:
            from telethon.tl.functions.channels import ExportInviteRequest
            peer = await client.get_input_entity(chat_id)
            res = await call_with_retry(client, ExportInviteRequest(channel=peer))
            return res.link
        else:
            # Positive legacy chat ID
            legacy_id = abs(chat_id) if isinstance(chat_id, int) else chat_id
            res = await call_with_retry(client, ExportChatInviteRequest(chat_id=legacy_id))
            return res.link
    except Exception as e:
        logger.error(f"Failed to export invite link: {e}")
        return None

async def kick_user(client: TelegramClient, chat_entity: Any, user_str: Union[str, int]) -> None:
    """Kicks/removes a user from a legacy group or supergroup/channel."""
    try:
        user_ent = await resolve_user_entity(client, user_str)
        peer = await client.get_input_entity(chat_entity)
        if isinstance(peer, types.InputPeerChannel):
            from telethon.tl.functions.channels import EditBannedRequest
            from telethon.tl.types import ChatBannedRights
            # Banning with view_messages=True restricts their view and effectively kicks them from a megagroup
            await call_with_retry(client, EditBannedRequest(
                channel=peer,
                participant=user_ent,
                banned_rights=ChatBannedRights(
                    until_date=None,
                    view_messages=True
                )
            ))
        elif isinstance(peer, types.InputPeerChat):
            await call_with_retry(client, DeleteChatUserRequest(
                chat_id=peer.chat_id,
                user_id=user_ent
            ))
        else:
            chat_id = utils.get_peer_id(chat_entity)
            if str(chat_id).startswith("-100"):
                from telethon.tl.functions.channels import EditBannedRequest
                from telethon.tl.types import ChatBannedRights
                await call_with_retry(client, EditBannedRequest(
                    channel=chat_entity,
                    participant=user_ent,
                    banned_rights=ChatBannedRights(
                        until_date=None,
                        view_messages=True
                    )
                ))
            else:
                await call_with_retry(client, DeleteChatUserRequest(
                    chat_id=abs(chat_id),
                    user_id=user_ent
                ))
    except Exception as e:
        logger.error(f"Failed to kick user {user_str} from chat {chat_entity}: {e}")
