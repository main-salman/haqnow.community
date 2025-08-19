import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import socketio
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Document, User

logger = logging.getLogger(__name__)

# Create Socket.IO server
sio = socketio.AsyncServer(cors_allowed_origins="*", logger=True, engineio_logger=True)

# Store active sessions and document rooms
active_sessions: Dict[str, Dict[str, Any]] = {}
document_rooms: Dict[int, Dict[str, Any]] = {}


class CollaborationManager:
    def __init__(self):
        self.annotations: Dict[int, List[Dict[str, Any]]] = {}
        self.comments: Dict[int, List[Dict[str, Any]]] = {}
        self.redactions: Dict[int, List[Dict[str, Any]]] = {}
        self.user_cursors: Dict[int, Dict[str, Dict[str, Any]]] = {}
        # Track redaction locks by document_id -> sid of locker
        self.redaction_locks: Dict[int, Optional[str]] = {}

    def get_document_state(self, document_id: int) -> Dict[str, Any]:
        """Get the current state of a document"""
        return {
            "annotations": self.annotations.get(document_id, []),
            "comments": self.comments.get(document_id, []),
            "redactions": self.redactions.get(document_id, []),
            "user_cursors": self.user_cursors.get(document_id, {}),
        }

    def add_annotation(
        self, document_id: int, annotation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add an annotation to a document"""
        if document_id not in self.annotations:
            self.annotations[document_id] = []

        annotation_id = f"ann_{len(self.annotations[document_id])}"
        annotation.update(
            {
                "id": annotation_id,
                "created_at": datetime.utcnow().isoformat(),
                "type": "annotation",
            }
        )

        self.annotations[document_id].append(annotation)
        return annotation

    def add_comment(self, document_id: int, comment: Dict[str, Any]) -> Dict[str, Any]:
        """Add a comment to a document"""
        if document_id not in self.comments:
            self.comments[document_id] = []

        comment_id = f"comment_{len(self.comments[document_id])}"
        comment.update(
            {
                "id": comment_id,
                "created_at": datetime.utcnow().isoformat(),
                "type": "comment",
            }
        )

        self.comments[document_id].append(comment)
        return comment

    def add_redaction(
        self, document_id: int, redaction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a redaction to a document"""
        if document_id not in self.redactions:
            self.redactions[document_id] = []

        redaction_id = f"redact_{len(self.redactions[document_id])}"
        redaction.update(
            {
                "id": redaction_id,
                "created_at": datetime.utcnow().isoformat(),
                "type": "redaction",
            }
        )

        self.redactions[document_id].append(redaction)
        return redaction

    def update_user_cursor(
        self, document_id: int, user_id: str, cursor_data: Dict[str, Any]
    ):
        """Update user cursor position"""
        if document_id not in self.user_cursors:
            self.user_cursors[document_id] = {}

        self.user_cursors[document_id][user_id] = {
            **cursor_data,
            "updated_at": datetime.utcnow().isoformat(),
        }

    def remove_user_cursor(self, document_id: int, user_id: str):
        """Remove user cursor when they disconnect"""
        if (
            document_id in self.user_cursors
            and user_id in self.user_cursors[document_id]
        ):
            del self.user_cursors[document_id][user_id]

    def acquire_redaction_lock(self, document_id: int, sid: str) -> bool:
        """Attempt to acquire the redaction lock for a document"""
        current = self.redaction_locks.get(document_id)
        if current is None:
            self.redaction_locks[document_id] = sid
            return True
        return current == sid

    def release_redaction_lock(self, document_id: int, sid: str) -> bool:
        """Release the redaction lock if held by this sid"""
        current = self.redaction_locks.get(document_id)
        if current == sid:
            self.redaction_locks[document_id] = None
            return True
        return False

    def remove_comment(self, document_id: int, comment_id: str) -> bool:
        if document_id not in self.comments:
            return False
        before = len(self.comments[document_id])
        self.comments[document_id] = [
            c for c in self.comments[document_id] if c.get("id") != comment_id
        ]
        return len(self.comments[document_id]) < before

    def remove_redaction(self, document_id: int, redaction_id: str) -> bool:
        if document_id not in self.redactions:
            return False
        before = len(self.redactions[document_id])
        self.redactions[document_id] = [
            r for r in self.redactions[document_id] if r.get("id") != redaction_id
        ]
        return len(self.redactions[document_id]) < before


# Global collaboration manager
collaboration_manager = CollaborationManager()


@sio.event
async def connect(sid, environ, auth):
    """Handle client connection"""
    logger.info(f"Client {sid} connected")

    # Store session info
    active_sessions[sid] = {
        "connected_at": datetime.utcnow().isoformat(),
        "user_id": auth.get("user_id") if auth else None,
        "user_name": auth.get("user_name") if auth else "Anonymous",
    }

    await sio.emit("connected", {"status": "connected"}, room=sid)


@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client {sid} disconnected")

    # Remove from all document rooms and clean up cursors
    if sid in active_sessions:
        session = active_sessions[sid]
        user_id = session.get("user_id")

        # Find and leave all document rooms
        for document_id, room_info in document_rooms.items():
            if sid in room_info.get("participants", {}):
                await leave_document(sid, {"document_id": document_id})

        del active_sessions[sid]
        # Release any redaction locks held by this sid
        for doc_id, locker in list(collaboration_manager.redaction_locks.items()):
            if locker == sid:
                collaboration_manager.redaction_locks[doc_id] = None


@sio.event
async def join_document(sid, data):
    """Join a document room for collaboration"""
    document_id = data.get("document_id")
    if not document_id:
        await sio.emit("error", {"message": "document_id is required"}, room=sid)
        return

    # Verify document exists
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            await sio.emit("error", {"message": "Document not found"}, room=sid)
            return
    finally:
        db.close()

    # Join the document room
    room_name = f"document_{document_id}"
    await sio.enter_room(sid, room_name)

    # Track participants
    if document_id not in document_rooms:
        document_rooms[document_id] = {"participants": {}}

    session = active_sessions.get(sid, {})
    document_rooms[document_id]["participants"][sid] = {
        "user_id": session.get("user_id"),
        "user_name": session.get("user_name"),
        "joined_at": datetime.utcnow().isoformat(),
    }

    # Send current document state to the new participant
    document_state = collaboration_manager.get_document_state(document_id)
    await sio.emit("document_state", document_state, room=sid)

    # Notify other participants
    participant_info = document_rooms[document_id]["participants"][sid]
    await sio.emit(
        "user_joined",
        {
            "user_id": participant_info["user_id"],
            "user_name": participant_info["user_name"],
        },
        room=room_name,
        skip_sid=sid,
    )

    logger.info(f"Client {sid} joined document {document_id}")


@sio.event
async def leave_document(sid, data):
    """Leave a document room"""
    document_id = data.get("document_id")
    if not document_id:
        return

    room_name = f"document_{document_id}"
    await sio.leave_room(sid, room_name)

    # Remove from participants and clean up cursor
    if (
        document_id in document_rooms
        and sid in document_rooms[document_id]["participants"]
    ):
        participant_info = document_rooms[document_id]["participants"][sid]
        user_id = participant_info.get("user_id")

        del document_rooms[document_id]["participants"][sid]

        # Remove user cursor
        if user_id:
            collaboration_manager.remove_user_cursor(document_id, user_id)

        # Notify other participants
        await sio.emit(
            "user_left",
            {"user_id": user_id, "user_name": participant_info.get("user_name")},
            room=room_name,
        )

    logger.info(f"Client {sid} left document {document_id}")


@sio.event
async def add_annotation(sid, data):
    """Add an annotation to a document"""
    document_id = data.get("document_id")
    annotation_data = data.get("annotation")

    if not document_id or not annotation_data:
        await sio.emit(
            "error", {"message": "document_id and annotation are required"}, room=sid
        )
        return

    # Add user info to annotation
    session = active_sessions.get(sid, {})
    annotation_data.update(
        {"user_id": session.get("user_id"), "user_name": session.get("user_name")}
    )

    # Add annotation
    annotation = collaboration_manager.add_annotation(document_id, annotation_data)

    # Broadcast to all participants in the document
    room_name = f"document_{document_id}"
    await sio.emit(
        "annotation_added",
        {"document_id": document_id, "annotation": annotation},
        room=room_name,
    )

    logger.info(
        f"Annotation added to document {document_id} by {session.get('user_name')}"
    )


@sio.event
async def add_comment(sid, data):
    """Add a comment to a document"""
    document_id = data.get("document_id")
    comment_data = data.get("comment")

    if not document_id or not comment_data:
        await sio.emit(
            "error", {"message": "document_id and comment are required"}, room=sid
        )
        return

    # Add user info to comment
    session = active_sessions.get(sid, {})
    comment_data.update(
        {"user_id": session.get("user_id"), "user_name": session.get("user_name")}
    )

    # Add comment
    comment = collaboration_manager.add_comment(document_id, comment_data)

    # Broadcast to all participants in the document
    room_name = f"document_{document_id}"
    await sio.emit(
        "comment_added",
        {"document_id": document_id, "comment": comment},
        room=room_name,
    )

    logger.info(
        f"Comment added to document {document_id} by {session.get('user_name')}"
    )


@sio.event
async def add_redaction(sid, data):
    """Add a redaction to a document"""
    document_id = data.get("document_id")
    redaction_data = data.get("redaction")

    if not document_id or not redaction_data:
        await sio.emit(
            "error", {"message": "document_id and redaction are required"}, room=sid
        )
        return

    # Add user info to redaction
    session = active_sessions.get(sid, {})
    redaction_data.update(
        {"user_id": session.get("user_id"), "user_name": session.get("user_name")}
    )

    # Add redaction (live overlay only)
    redaction = collaboration_manager.add_redaction(document_id, redaction_data)

    # Broadcast to all participants in the document
    room_name = f"document_{document_id}"
    await sio.emit(
        "redaction_added",
        {"document_id": document_id, "redaction": redaction},
        room=room_name,
    )

    logger.info(
        f"Redaction added to document {document_id} by {session.get('user_name')}"
    )


@sio.event
async def delete_comment(sid, data):
    document_id = data.get("document_id")
    comment_id = data.get("comment_id")
    if not document_id or not comment_id:
        await sio.emit(
            "error", {"message": "document_id and comment_id are required"}, room=sid
        )
        return
    removed = collaboration_manager.remove_comment(document_id, comment_id)
    room_name = f"document_{document_id}"
    if removed:
        await sio.emit(
            "comment_deleted",
            {"document_id": document_id, "comment_id": comment_id},
            room=room_name,
        )


@sio.event
async def delete_redaction(sid, data):
    document_id = data.get("document_id")
    redaction_id = data.get("redaction_id")
    if not document_id or not redaction_id:
        await sio.emit(
            "error", {"message": "document_id and redaction_id are required"}, room=sid
        )
        return
    removed = collaboration_manager.remove_redaction(document_id, redaction_id)
    room_name = f"document_{document_id}"
    if removed:
        await sio.emit(
            "redaction_deleted",
            {"document_id": document_id, "redaction_id": redaction_id},
            room=room_name,
        )


@sio.event
async def acquire_redaction_lock(sid, data):
    """Attempt to acquire document-level redaction lock (first editor wins)"""
    document_id = data.get("document_id")
    if not document_id:
        await sio.emit("error", {"message": "document_id is required"}, room=sid)
        return
    ok = collaboration_manager.acquire_redaction_lock(document_id, sid)
    await sio.emit(
        "redaction_lock_status",
        {"document_id": document_id, "acquired": ok},
        room=sid,
    )
    if ok:
        room_name = f"document_{document_id}"
        await sio.emit(
            "redaction_lock_acquired",
            {"document_id": document_id},
            room=room_name,
            skip_sid=sid,
        )


@sio.event
async def release_redaction_lock(sid, data):
    """Release document-level redaction lock if held"""
    document_id = data.get("document_id")
    if not document_id:
        return
    released = collaboration_manager.release_redaction_lock(document_id, sid)
    if released:
        room_name = f"document_{document_id}"
        await sio.emit(
            "redaction_lock_released",
            {"document_id": document_id},
            room=room_name,
        )


@sio.event
async def update_cursor(sid, data):
    """Update user cursor position"""
    document_id = data.get("document_id")
    cursor_data = data.get("cursor")

    if not document_id or not cursor_data:
        return

    session = active_sessions.get(sid, {})
    user_id = session.get("user_id")

    if not user_id:
        return

    # Update cursor position
    collaboration_manager.update_user_cursor(
        document_id, user_id, {**cursor_data, "user_name": session.get("user_name")}
    )

    # Broadcast cursor update to other participants
    room_name = f"document_{document_id}"
    await sio.emit(
        "cursor_updated",
        {
            "document_id": document_id,
            "user_id": user_id,
            "user_name": session.get("user_name"),
            "cursor": cursor_data,
        },
        room=room_name,
        skip_sid=sid,
    )


@sio.event
async def get_participants(sid, data):
    """Get list of current participants in a document"""
    document_id = data.get("document_id")
    if not document_id:
        await sio.emit("error", {"message": "document_id is required"}, room=sid)
        return

    participants = []
    if document_id in document_rooms:
        for participant_sid, info in document_rooms[document_id][
            "participants"
        ].items():
            participants.append(
                {
                    "user_id": info.get("user_id"),
                    "user_name": info.get("user_name"),
                    "joined_at": info.get("joined_at"),
                }
            )

    await sio.emit(
        "participants_list",
        {"document_id": document_id, "participants": participants},
        room=sid,
    )


# Create ASGI app for Socket.IO
collaboration_app = socketio.ASGIApp(sio, other_asgi_app=None)
