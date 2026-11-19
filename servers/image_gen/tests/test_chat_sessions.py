"""
Tests for Persistent Dynamic Chat Sessions in Gemini Nano Backend.
Validates SQLite storage, thread safety, multi-turn context tracking,
FastAPI REST endpoints (/api/sessions), and auto-logging from /api/generate and /api/edit.
"""

import os
import pytest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from runtime_server import app
from app.storage.chat_store import ChatStore, default_store
import app.storage.chat_store as chat_store_module


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestChatStoreUnit:
    """Direct unit tests for ChatStore class & persistence."""

    def test_persistence_across_instances(self, tmp_path):
        db_file = tmp_path / "test_chat.db"
        
        # Instance A: create session and messages
        store_a = ChatStore(db_path=db_file)
        session = store_a.create_session(title="Persistent Session A")
        sid = session["id"]
        assert sid.startswith("sess_")
        assert session["title"] == "Persistent Session A"
        assert session["messages"] == []

        msg1 = store_a.add_message(
            session_id=sid,
            role="user",
            content="Generate a hyperrealistic sunset",
            metadata={"priority": "high"}
        )
        assert msg1["role"] == "user"
        assert msg1["content"] == "Generate a hyperrealistic sunset"

        msg2 = store_a.add_message(
            session_id=sid,
            role="assistant",
            content="Here is your sunset",
            image_path=str(tmp_path / "sunset.png"),
            metadata={"steps": 5, "cfg": 7.0}
        )
        assert msg2["image_url"] == "/api/image/sunset.png"

        # Instance B: open the same DB file in a fresh instance
        store_b = ChatStore(db_path=db_file)
        fetched = store_b.get_session(sid)
        assert fetched is not None
        assert fetched["id"] == sid
        assert fetched["title"] == "Persistent Session A"
        assert fetched["message_count"] == 2
        assert len(fetched["messages"]) == 2
        assert fetched["messages"][0]["content"] == "Generate a hyperrealistic sunset"
        assert fetched["messages"][0]["metadata"] == {"priority": "high"}
        assert fetched["messages"][1]["role"] == "assistant"
        assert fetched["messages"][1]["metadata"] == {"steps": 5, "cfg": 7.0}
        assert fetched["active_image_path"] == str(tmp_path / "sunset.png")
        assert fetched["active_image_id"] == "sunset"

        # Instance C: test deletion and cascade
        store_c = ChatStore(db_path=db_file)
        deleted = store_c.delete_session(sid)
        assert deleted is True

        assert store_c.get_session(sid) is None
        # Check raw database tables for cascade
        with store_c._get_conn() as conn:
            m_count = conn.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (sid,)).fetchone()[0]
            assert m_count == 0

    def test_thread_safe_concurrency(self, tmp_path):
        db_file = tmp_path / "concurrent_chat.db"
        store = ChatStore(db_path=db_file)
        session = store.create_session(title="Concurrent Stress Test")
        sid = session["id"]

        def worker_task(index: int):
            # Concurrent message additions and session updates
            store.add_message(
                session_id=sid,
                role="user" if index % 2 == 0 else "assistant",
                content=f"Message index {index}",
                metadata={"worker": index}
            )
            store.update_session(session_id=sid, title=f"Concurrent Test Title {index}")

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker_task, i) for i in range(25)]
            for f in futures:
                f.result()

        final_sess = store.get_session(sid)
        assert final_sess is not None
        assert final_sess["message_count"] == 25
        assert len(final_sess["messages"]) == 25


class TestChatSessionEndpoints:
    """Integration tests for /api/sessions REST API."""

    def test_create_session_defaults(self, client):
        resp = client.post("/api/sessions", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["id"].startswith("sess_")
        assert data["title"] == "New Chat"
        assert data["messages"] == []
        assert data["active_image_path"] is None

    def test_create_session_custom_title(self, client):
        resp = client.post("/api/sessions", json={"title": "Concept Design Workspace"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Concept Design Workspace"

    def test_list_sessions(self, client):
        # Create two distinct sessions
        s1 = client.post("/api/sessions", json={"title": "Session List Test 1"}).json()
        s2 = client.post("/api/sessions", json={"title": "Session List Test 2"}).json()

        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        sessions = resp.json()
        assert isinstance(sessions, list)
        assert len(sessions) >= 2

        s_ids = [s["id"] for s in sessions]
        assert s1["id"] in s_ids
        assert s2["id"] in s_ids

        # Validate summary fields
        for s in sessions:
            assert "id" in s
            assert "title" in s
            assert "message_count" in s
            assert "updated_at" in s
            assert "preview_image" in s

    def test_get_session_details_and_not_found(self, client):
        create_resp = client.post("/api/sessions", json={"title": "Detail Test"}).json()
        sid = create_resp["id"]

        detail_resp = client.get(f"/api/sessions/{sid}")
        assert detail_resp.status_code == 200
        data = detail_resp.json()
        assert data["id"] == sid
        assert data["title"] == "Detail Test"
        assert data["messages"] == []

        # 404 for non-existent session
        nf_resp = client.get("/api/sessions/sess_nonexistent_999")
        assert nf_resp.status_code == 404
        assert "not found" in nf_resp.json()["detail"].lower()

    def test_update_session_title_and_active_context(self, client):
        create_resp = client.post("/api/sessions", json={"title": "Old Name"}).json()
        sid = create_resp["id"]

        # Update title
        up_resp = client.put(f"/api/sessions/{sid}", json={"title": "Renamed Workspace"})
        assert up_resp.status_code == 200
        assert up_resp.json()["title"] == "Renamed Workspace"

        # Update active image path
        sample_path = str(Path(__file__).resolve().parents[1] / "outputs" / "ref_sample.png")
        up_context = client.put(
            f"/api/sessions/{sid}",
            json={"active_image_path": sample_path}
        )
        assert up_context.status_code == 200
        assert up_context.json()["active_image_path"] == sample_path
        assert up_context.json()["active_image_id"] == "ref_sample"

        # Non-existent session 404
        nf_resp = client.put("/api/sessions/sess_nonexistent_999", json={"title": "Nope"})
        assert nf_resp.status_code == 404

    def test_add_manual_message(self, client):
        create_resp = client.post("/api/sessions", json={"title": "Message Test"}).json()
        sid = create_resp["id"]

        # Add user message
        user_msg = client.post(
            f"/api/sessions/{sid}/messages",
            json={
                "role": "user",
                "content": "Can you design a retro neon arcade?",
                "metadata": {"client_timestamp": 12345678}
            }
        )
        assert user_msg.status_code == 200
        u_data = user_msg.json()
        assert u_data["role"] == "user"
        assert u_data["content"] == "Can you design a retro neon arcade?"
        assert u_data["metadata"]["client_timestamp"] == 12345678

        # Add assistant message with image URL
        asst_msg = client.post(
            f"/api/sessions/{sid}/messages",
            json={
                "role": "assistant",
                "content": "Here is the arcade scene.",
                "image_path": "/outputs/arcade_01.png",
                "metadata": {"style": "neon"}
            }
        )
        assert asst_msg.status_code == 200
        a_data = asst_msg.json()
        assert a_data["role"] == "assistant"
        assert a_data["image_url"] == "/api/image/arcade_01.png"

        # Verify session message history
        sess = client.get(f"/api/sessions/{sid}").json()
        assert sess["message_count"] == 2
        assert len(sess["messages"]) == 2
        assert sess["messages"][0]["id"] == u_data["id"]
        assert sess["messages"][1]["id"] == a_data["id"]

        # Non-existent session 404
        nf_resp = client.post("/api/sessions/sess_invalid/messages", json={"role": "user", "content": "test"})
        assert nf_resp.status_code == 404

    def test_delete_session(self, client):
        create_resp = client.post("/api/sessions", json={"title": "To Delete"}).json()
        sid = create_resp["id"]

        # Add a message to verify cascade
        client.post(f"/api/sessions/{sid}/messages", json={"role": "user", "content": "Temporary message"})

        del_resp = client.delete(f"/api/sessions/{sid}")
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

        # Ensure subsequent get returns 404
        assert client.get(f"/api/sessions/{sid}").status_code == 404

        # Non-existent session delete returns 404
        assert client.delete(f"/api/sessions/{sid}").status_code == 404


class TestSessionGenerationAndEditIntegration:
    """Validates dynamic session recording through /api/generate and /api/edit."""

    def test_generate_auto_records_to_session(self, client):
        # 1. Create session
        s_resp = client.post("/api/sessions", json={"title": "Gen Session Test"}).json()
        sid = s_resp["id"]

        # 2. Trigger generation with session_id
        gen_resp = client.post(
            "/api/generate",
            json={
                "prompt": "serene mountain lake at twilight with starry sky",
                "style": "photorealistic",
                "aspect_ratio": "16:9",
                "steps": 1,
                "seed": 888,
                "session_id": sid,
                "run_qa": True
            }
        )
        assert gen_resp.status_code == 200
        gen_data = gen_resp.json()
        assert gen_data["success"] is True
        assert gen_data["session_id"] == sid
        assert "user_message_id" in gen_data
        assert "assistant_message_id" in gen_data
        gen_filepath = gen_data["file_path"]

        # 3. Verify session history has user and assistant messages
        sess = client.get(f"/api/sessions/{sid}").json()
        assert sess["message_count"] == 2
        assert len(sess["messages"]) == 2

        user_msg = sess["messages"][0]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "serene mountain lake at twilight with starry sky"

        asst_msg = sess["messages"][1]
        assert asst_msg["role"] == "assistant"
        assert asst_msg["image_path"] == gen_filepath
        assert asst_msg["image_url"] == f"/api/image/{Path(gen_filepath).name}"
        assert asst_msg["metadata"]["qa_report"] is not None

        # 4. Verify session active context is updated
        assert sess["active_image_path"] == gen_filepath

        # 5. Verify sessions list shows latest preview_image
        sess_list = client.get("/api/sessions").json()
        target_s = next(s for s in sess_list if s["id"] == sid)
        assert target_s["preview_image"] == f"/api/image/{Path(gen_filepath).name}"

    def test_conversational_edit_uses_session_context(self, client):
        # 1. Create session and generate initial image
        s_resp = client.post("/api/sessions", json={"title": "Multi-Turn Editing Session"}).json()
        sid = s_resp["id"]

        gen_resp = client.post(
            "/api/generate",
            json={
                "prompt": "golden retriever playing in green autumn park",
                "style": "photorealistic",
                "steps": 1,
                "seed": 999,
                "session_id": sid
            }
        ).json()
        initial_image_path = gen_resp["file_path"]

        # 2. Edit without passing image_source: should use active_image_path from session
        edit_resp = client.post(
            "/api/edit",
            json={
                "session_id": sid,
                "filter_preset": "hdr",
                "brightness": 1.1,
                "contrast": 1.15,
                "run_qa": True
            }
        )
        assert edit_resp.status_code == 200
        edit_data = edit_resp.json()
        assert edit_data["success"] is True
        assert edit_data["session_id"] == sid
        edited_image_path = edit_data["file_path"]
        assert edited_image_path != initial_image_path

        # 3. Verify session now has 4 messages and updated active_image_path
        sess = client.get(f"/api/sessions/{sid}").json()
        assert sess["message_count"] == 4
        assert len(sess["messages"]) == 4

        # Edit user message
        edit_user = sess["messages"][2]
        assert edit_user["role"] == "user"
        assert "hdr" in edit_user["content"].lower()

        # Edit assistant message
        edit_asst = sess["messages"][3]
        assert edit_asst["role"] == "assistant"
        assert edit_asst["image_path"] == edited_image_path
        assert edit_asst["metadata"]["filter_preset"] == "hdr"

        # Active image path updated to the new edited image
        assert sess["active_image_path"] == edited_image_path

    def test_multi_turn_conversational_context_prompt_resolution(self, client):
        """Test that follow-up prompts in a chat session inherit context and entities from previous turns."""
        s_resp = client.post("/api/sessions", json={"title": "Contextual Evolution Session"}).json()
        sid = s_resp["id"]

        # Turn 1: Initial prompt
        res1 = client.post(
            "/api/generate",
            json={
                "prompt": "sleek aerodynamic cybernetic hovercraft over crimson canyon",
                "style": "cyberpunk",
                "steps": 1,
                "seed": 101,
                "session_id": sid
            }
        ).json()
        assert res1["success"] is True

        # Turn 2: Follow-up prompt with delta phrasing ("now make it night time and add searchlights")
        res2 = client.post(
            "/api/generate",
            json={
                "prompt": "now make it night time with searchlights beaming down",
                "style": "cyberpunk",
                "steps": 1,
                "seed": 102,
                "session_id": sid
            }
        ).json()
        assert res2["success"] is True

        # Verify that Turn 2 resolved contextually by retaining the hovercraft from Turn 1
        prompt_used = res2["prompt_used"].lower()
        assert "hovercraft" in prompt_used
        assert "searchlights" in prompt_used

    def test_multi_image_input_conditioning(self, client):
        """Test multi-image input support across /api/generate and /api/edit."""
        # 1. Create 2 test base images
        res1 = client.post("/api/generate", json={"prompt": "abstract red geometric shapes", "steps": 1, "seed": 1}).json()
        res2 = client.post("/api/generate", json={"prompt": "abstract blue fluid waves", "steps": 1, "seed": 2}).json()

        img1_b64 = res1["image_base64"]
        img2_b64 = res2["image_base64"]

        # 2. Test multi-image conditioning in /api/generate
        multi_gen = client.post(
            "/api/generate",
            json={
                "prompt": "blend the energy of both abstract artworks",
                "image_sources": [img1_b64, img2_b64],
                "steps": 1,
                "seed": 42
            }
        )
        assert multi_gen.status_code == 200
        data_gen = multi_gen.json()
        assert data_gen["success"] is True
        assert "multi-image" in str(data_gen["audit_log"]).lower()

        # 3. Test multi-image composition in /api/edit
        multi_edit = client.post(
            "/api/edit",
            json={
                "image_sources": [img1_b64, img2_b64],
                "edit_mode": "transform",
                "filter_preset": "dramatic",
                "brightness": 1.1,
                "contrast": 1.2
            }
        )
        assert multi_edit.status_code == 200
        data_edit = multi_edit.json()
        assert data_edit["success"] is True
