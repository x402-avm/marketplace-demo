import pytest
from PIL import Image
from unittest.mock import patch, AsyncMock, MagicMock

from app.agents.prompt_optimizer import PromptOptimizerAgent, OptimizationResult, SceneGraph
from app.agents.orchestrator import AgentOrchestrator
from app.storage.chat_store import ChatStore
from app.utils.image_utils import image_to_base64
from app.utils.oom_guard import oom_guard


@pytest.fixture
def optimizer():
    return PromptOptimizerAgent()


# ==============================================================================
# 1. Anti-Bleeding for Conjoined Entities Without Prepositions
# ==============================================================================

def test_conjoined_entities_anti_bleeding(optimizer):
    """Verify conjoined entities (e.g. 'a blue cat and a yellow dog') receive semantic boundary clauses."""
    prompt = "a blue cat and a yellow dog"
    sg = optimizer.decompose_scene(prompt)
    assert len(sg.entities) == 2
    assert len(sg.relations) == 0

    assert "strict semantic boundaries without cross-attribute bleeding" in sg.synthesized_prompt
    assert "blue characteristics belong strictly to the cat" in sg.synthesized_prompt
    assert "yellow characteristics belong strictly to the dog" in sg.synthesized_prompt

    res = optimizer.optimize(prompt)
    assert "strict semantic boundaries" in res["optimized_prompt"]
    assert "thinking_trace" in res
    assert len(res["thinking_trace"]) >= 4
    assert res["thinking_trace"][0].startswith("1. Decomposed scene into 2 discrete entities")


def test_singular_entity_grammar(optimizer):
    """Verify singular entity formats '1 discrete entity' rather than plural 'entities'."""
    prompt = "a red apple"
    sg = optimizer.decompose_scene(prompt)
    assert len(sg.entities) == 1
    assert "1 discrete entity with explicit attribute bindings" in sg.thinking_trace[0]


# ==============================================================================
# 2. Conversational Delta Resolution & Semantic Replacement
# ==============================================================================

def test_delta_now_make_it_night(optimizer):
    """Turn 1: sunny desert -> Turn 2: 'now make it night' evicts sunny, adds night."""
    chat_hist = [
        {"role": "user", "content": "a futuristic sports car parked on a sunny desert highway"},
        {"role": "assistant", "content": "Generated image", "metadata": {"context_resolved_prompt": "a futuristic sports car parked on a sunny desert highway"}}
    ]
    resolved = optimizer.resolve_conversational_context("now make it night", chat_history=chat_hist)
    res_lower = resolved.lower()
    assert "sports car" in res_lower
    assert "night" in res_lower
    assert "sunny" not in res_lower


def test_delta_add_sunglasses(optimizer):
    """Turn 1: astronaut -> Turn 2: 'add sunglasses' binds accessory to subject."""
    chat_hist = [
        {"role": "user", "content": "portrait of an astronaut in a white spacesuit"},
        {"role": "assistant", "content": "Generated image", "metadata": {"context_resolved_prompt": "portrait of an astronaut in a white spacesuit"}}
    ]
    resolved = optimizer.resolve_conversational_context("add sunglasses", chat_history=chat_hist)
    res_lower = resolved.lower()
    assert "astronaut" in res_lower
    assert "spacesuit" in res_lower
    assert "sunglasses" in res_lower


def test_delta_change_shirt_to_green(optimizer):
    """Turn 1: red shirt -> Turn 2: 'change shirt to green' replaces red with green."""
    chat_hist = [
        {"role": "user", "content": "a young woman in a red shirt standing in a park"},
        {"role": "assistant", "content": "Generated image", "metadata": {"context_resolved_prompt": "a young woman in a red shirt standing in a park"}}
    ]
    resolved = optimizer.resolve_conversational_context("change shirt to green", chat_history=chat_hist)
    res_lower = resolved.lower()
    assert "young woman" in res_lower
    assert "green shirt" in res_lower
    assert "red shirt" not in res_lower


def test_delta_three_turn_evolution(optimizer):
    """Turn 1 -> Turn 2 -> Turn 3 accumulates without losing core subject."""
    chat_hist = [
        {"role": "user", "content": "cyberpunk warrior on a neon rooftop"},
        {"role": "assistant", "content": "Generated 1", "metadata": {"context_resolved_prompt": "cyberpunk warrior on a neon rooftop"}},
        {"role": "user", "content": "now make it raining"},
        {"role": "assistant", "content": "Generated 2", "metadata": {"context_resolved_prompt": "cyberpunk warrior on a neon rooftop, raining"}},
    ]
    resolved = optimizer.resolve_conversational_context("add a glowing katana", chat_history=chat_hist)
    res_lower = resolved.lower()
    assert "cyberpunk warrior" in res_lower
    assert "rooftop" in res_lower
    assert "raining" in res_lower
    assert "katana" in res_lower


def test_delta_entity_substitution(optimizer):
    """Replace dog with cat preserves couch background."""
    chat_hist = [
        {"role": "user", "content": "golden retriever sitting on a red couch"},
        {"role": "assistant", "content": "Generated", "metadata": {"context_resolved_prompt": "golden retriever sitting on a red couch"}}
    ]
    resolved = optimizer.resolve_conversational_context("replace the dog with a black cat", chat_history=chat_hist)
    res_lower = resolved.lower()
    assert "cat" in res_lower
    assert "black" in res_lower
    assert "red couch" in res_lower
    assert "retriever" not in res_lower
    assert "dog" not in res_lower


def test_delta_entity_removal(optimizer):
    """Remove fedora hat preserves trench coat and detective."""
    chat_hist = [
        {"role": "user", "content": "detective in a trench coat wearing a fedora hat"},
        {"role": "assistant", "content": "Generated", "metadata": {"context_resolved_prompt": "detective in a trench coat wearing a fedora hat"}}
    ]
    resolved = optimizer.resolve_conversational_context("remove the fedora hat", chat_history=chat_hist)
    res_lower = resolved.lower()
    assert "detective" in res_lower
    assert "trench coat" in res_lower
    assert "fedora hat" not in res_lower


def test_independent_prompt_retains_isolation(optimizer):
    """Independent prompt without delta phrasing does not chain."""
    chat_hist = [
        {"role": "user", "content": "red sports car on highway"}
    ]
    resolved = optimizer.resolve_conversational_context("a blue butterfly flying", chat_history=chat_hist)
    assert "sports car" not in resolved
    assert resolved == "a blue butterfly flying"


# ==============================================================================
# 3. Image Editing CoT Reasoning Pass
# ==============================================================================

def test_optimize_edit_with_reasoning_single(optimizer):
    """Verify single-image edit produces 4-step thinking trace and preservation notes."""
    res = optimizer.optimize_edit_with_reasoning(
        instruction="add a glowing crown on the lion's head",
        parent_prompt="a golden lion in savanna",
        num_images=1
    )
    assert isinstance(res, OptimizationResult)
    assert len(res["thinking_trace"]) == 4
    assert "crown" in res["optimized_prompt"]
    assert "<|im_start|>system" in res["optimized_prompt"]
    assert "Picture 1: <|vision_start|><|image_pad|><|vision_end|>" in res["optimized_prompt"]
    assert "preservation_notes" in res
    assert "Preserving" in res["preservation_notes"]


def test_optimize_edit_with_reasoning_multi_image(optimizer):
    """Verify multi-image edit attributes roles across references."""
    res = optimizer.optimize_edit_with_reasoning(
        instruction="combine foreground character from picture 1 into background of picture 2",
        num_images=2
    )
    assert len(res["thinking_trace"]) == 4
    assert "Picture 1: <|vision_start|><|image_pad|><|vision_end|>" in res["optimized_prompt"]
    assert "Picture 2: <|vision_start|><|image_pad|><|vision_end|>" in res["optimized_prompt"]
    assert "Picture 1" in res["preservation_notes"]
    assert "Picture 2" in res["preservation_notes"]


# ==============================================================================
# 4. Orchestrator Top-Level Contracts & CoT Latency Profiling
# ==============================================================================

@pytest.mark.asyncio
async def test_orchestrator_cot_contracts_and_metrics():
    """Verify AgentOrchestrator returns top-level thinking_trace, cot_reasoning, and latency metrics."""
    mock_generator = MagicMock()
    mock_generator.generate_text_to_image = AsyncMock(return_value=(
        Image.new("RGB", (512, 512), color=(10, 10, 10)),
        {
            "width": 512,
            "height": 512,
            "latency_seconds": 0.5,
            "stage_metrics": {
                "stage_1_text_encoder_seconds": 0.1,
                "stage_2_dit_sampling_seconds": 0.3,
                "stage_3_vae_decode_seconds": 0.1
            }
        }
    ))
    mock_generator.generate_image_to_image = AsyncMock(return_value=(
        Image.new("RGB", (512, 512), color=(20, 20, 20)),
        {
            "width": 512,
            "height": 512,
            "latency_seconds": 0.6,
            "strength": 0.5,
            "stage_metrics": {
                "stage_1_vision_text_encoder_seconds": 0.1,
                "stage_2_dit_sampling_seconds": 0.4,
                "stage_3_vae_decode_seconds": 0.1
            }
        }
    ))

    orchestrator = AgentOrchestrator(generator=mock_generator)

    with patch.object(oom_guard, "preflight_check", return_value=(True, "OK")):
        # 1. Text-to-Image test
        res_t2i = await orchestrator.orchestrate_text_to_image(
            prompt="blue cat on yellow box",
            run_qa=True
        )
        assert res_t2i["success"] is True
        assert "thinking_trace" in res_t2i
        assert isinstance(res_t2i["thinking_trace"], list)
        assert len(res_t2i["thinking_trace"]) >= 4
        assert "cot_reasoning" in res_t2i
        assert res_t2i["thought_image_url"] is None
        assert res_t2i["thought_image_base64"] is None
        assert "cot_reasoning_seconds" in res_t2i["stage_metrics"]
        assert "cot_reasoning_ms" in res_t2i["stage_metrics"]
        assert res_t2i["stage_metrics"]["cot_reasoning_seconds"] >= 0.0

        # 2. Image Edit test
        sample_img = Image.new("RGB", (512, 512), color=(30, 30, 30))
        res_edit = await orchestrator.orchestrate_image_edit(
            image_source=image_to_base64(sample_img),
            prompt="change color to red",
            strength=0.5,
            run_qa=True
        )
        assert res_edit["success"] is True
        assert "thinking_trace" in res_edit
        assert isinstance(res_edit["thinking_trace"], list)
        assert len(res_edit["thinking_trace"]) >= 4
        assert "cot_reasoning" in res_edit
        assert res_edit["thought_image_url"] is None
        assert res_edit["thought_image_base64"] is None
        assert "cot_reasoning_seconds" in res_edit["stage_metrics"]
        assert "cot_reasoning_ms" in res_edit["stage_metrics"]


# ==============================================================================
# 5. ChatStore Lineage Messages
# ==============================================================================

def test_chat_store_lineage_branching(tmp_path):
    """Verify get_lineage_messages traverses edit branch correctly."""
    db_file = tmp_path / "test_chat.db"
    store = ChatStore(db_path=db_file)
    sess = store.create_session(title="Lineage Test")
    sid = sess["id"]

    m1 = store.add_message(sid, role="user", content="Initial prompt")
    m2 = store.add_message(sid, role="assistant", content="Initial render")

    # Branch A
    m3_a = store.add_message(sid, role="user", content="Edit A", edit_parent_id=m2["id"])
    m4_a = store.add_message(sid, role="assistant", content="Render A", edit_parent_id=m3_a["id"])

    # Branch B (branched from m2)
    m3_b = store.add_message(sid, role="user", content="Edit B", edit_parent_id=m2["id"])
    m4_b = store.add_message(sid, role="assistant", content="Render B", edit_parent_id=m3_b["id"])

    lineage_b = store.get_lineage_messages(sid, edit_parent_id=m4_b["id"])
    lineage_b_ids = [m["id"] for m in lineage_b]

    assert m4_b["id"] in lineage_b_ids
    assert m3_b["id"] in lineage_b_ids
    assert m2["id"] in lineage_b_ids
    assert m4_a["id"] not in lineage_b_ids
    assert m3_a["id"] not in lineage_b_ids
