import pytest
import json
from app.agents.prompt_optimizer import (
    PromptOptimizerAgent,
    STYLE_PRESETS,
    OptimizationResult,
    SceneGraph,
    EntityAttribute,
    SpatialRelation,
    optimize_edit_instruction,
    OFFICIAL_CHATML_EDIT_SYSTEM_PROMPT
)

FORBIDDEN_BUZZWORDS = [
    "award-winning",
    "masterpiece",
    "8k resolution",
    "8k uhd",
    "8k",
    "octane render",
    "masterwork",
    "worst quality",
    "low quality",
    "normal quality",
    "blockbuster movie",
    "magazine cover quality",
    "epic fantasy art"
]


def test_prompt_optimizer_basic():
    optimizer = PromptOptimizerAgent()
    res = optimizer.optimize("a vintage roadster on coastal highway", style="photorealistic")
    assert "roadster" in res["optimized_prompt"]
    assert "photorealistic" in res["optimized_prompt"].lower() or "photographic" in res["optimized_prompt"].lower()
    assert "blurry" in res["negative_prompt"]
    assert res["recommended_steps"] > 0
    assert res["recommended_guidance"] > 0


def test_prompt_optimizer_styles():
    optimizer = PromptOptimizerAgent()
    for style in STYLE_PRESETS.keys():
        res = optimizer.optimize("neon city", style=style)
        assert res["style_applied"] == style
        assert len(res["optimized_prompt"]) > len("neon city")


def test_aspect_ratio_inference():
    optimizer = PromptOptimizerAgent()
    # Portrait keyword
    res_portrait = optimizer.optimize("studio portrait of a model woman")
    assert res_portrait["recommended_aspect_ratio"] == "9:16"
    
    # Landscape keyword
    res_landscape = optimizer.optimize("wide panorama view of majestic mountain horizon")
    assert res_landscape["recommended_aspect_ratio"] == "16:9"
    
    # Neutral keyword
    res_square = optimizer.optimize("abstract geometric sphere")
    assert res_square["recommended_aspect_ratio"] == "1:1"


def test_prompt_optimizer_edge_cases():
    optimizer = PromptOptimizerAgent()
    # Empty prompt
    res_empty = optimizer.optimize("")
    assert len(res_empty["optimized_prompt"]) > 0
    
    # Unknown style defaults gracefully
    res_unknown = optimizer.optimize("cat", style="non_existent_style_xyz")
    assert "optimized_prompt" in res_unknown
    
    # Custom negative prompt merged
    res_neg = optimizer.optimize("dog", negative_prompt="extra ears, green tint")
    assert "extra ears" in res_neg["negative_prompt"]
    assert "green tint" in res_neg["negative_prompt"]


def test_style_presets_no_legacy_buzzwords():
    """Verify that all STYLE_PRESETS and default negatives are purged of SD 1.5 tag-stuffing."""
    optimizer = PromptOptimizerAgent()
    
    # Check all presets
    for style_name, preset in STYLE_PRESETS.items():
        for field in ("prefix", "suffix", "negative"):
            text = preset[field].lower()
            for buzzword in FORBIDDEN_BUZZWORDS:
                assert buzzword not in text, (
                    f"Preset '{style_name}' field '{field}' contains obsolete buzzword '{buzzword}': {text}"
                )
    
    # Check agent default negative
    default_neg = optimizer.default_negative.lower()
    for buzzword in FORBIDDEN_BUZZWORDS:
        assert buzzword not in default_neg, (
            f"PromptOptimizerAgent.default_negative contains obsolete buzzword '{buzzword}': {default_neg}"
        )


def test_cot_scene_decomposition_complex_spatial():
    """Verify in-pipeline Chain-of-Thought scene decomposition for complex spatial prompts."""
    optimizer = PromptOptimizerAgent()
    prompt = "blue cat on yellow box next to red bicycle"
    
    scene_graph = optimizer.decompose_scene(prompt)
    assert isinstance(scene_graph, SceneGraph)
    assert len(scene_graph.entities) == 3
    assert len(scene_graph.relations) == 2
    
    # Verify entity attribute bindings
    e0, e1, e2 = scene_graph.entities
    assert e0.entity == "cat"
    assert e0.attributes == ["blue"]
    assert e0.spatial_role == "subject"
    
    assert e1.entity == "box"
    assert e1.attributes == ["yellow"]
    assert e1.spatial_role == "reference_object"
    
    assert e2.entity == "bicycle"
    assert e2.attributes == ["red"]
    
    # Verify spatial relations
    r0, r1 = scene_graph.relations
    assert r0.source == "cat"
    assert r0.preposition == "on top of"
    assert r0.target == "box"
    
    assert r1.source == "box"
    assert r1.preposition == "next to"
    assert r1.target == "bicycle"
    
    # Verify thinking trace
    trace = scene_graph.thinking_trace
    assert len(trace) >= 4
    assert any("Decomposed scene into 3 discrete entities" in t for t in trace)
    assert any("adjective-noun isolation" in t for t in trace)
    assert any("spatial relationship graph" in t for t in trace)
    
    # Verify synthesized prompt strictly binds attributes to nouns
    synth = scene_graph.synthesized_prompt
    assert "blue cat" in synth
    assert "yellow box" in synth
    assert "red bicycle" in synth
    assert "on top of" in synth
    assert "next to" in synth
    assert "cross-attribute bleeding" in synth or "strict semantic boundaries" in synth


def test_spatial_prepositions_variety():
    """Verify accurate extraction of diverse spatial prepositions."""
    optimizer = PromptOptimizerAgent()
    test_cases = [
        ("golden lion to the left of silver statue", "lion", "to the left of", "statue"),
        ("black cat behind white dog", "cat", "behind", "dog"),
        ("red car in front of blue house", "car", "in front of", "house"),
        ("green turtle underneath wooden bridge", "turtle", "underneath", "bridge"),
        ("flying eagle above snowy mountain", "eagle", "above", "mountain"),
        ("treasure chest inside dark cave", "chest", "inside", "cave"),
        ("flower garden around marble fountain", "garden", "around", "fountain"),
    ]
    
    for prompt, expected_src, expected_prep, expected_tgt in test_cases:
        sg = optimizer.decompose_scene(prompt)
        assert len(sg.relations) >= 1, f"Failed to extract relation from: {prompt}"
        rel = sg.relations[0]
        assert rel.source == expected_src, f"Expected source {expected_src}, got {rel.source}"
        assert rel.preposition == expected_prep, f"Expected prep {expected_prep}, got {rel.preposition}"
        assert rel.target == expected_tgt, f"Expected target {expected_tgt}, got {rel.target}"


def test_attribute_binding_anti_bleeding_in_optimize():
    """Verify full optimize pipeline integrates CoT without attribute bleeding."""
    optimizer = PromptOptimizerAgent()
    prompt = "blue cat on yellow box next to red bicycle"
    
    res = optimizer.optimize(prompt, style="photorealistic")
    assert isinstance(res, OptimizationResult)
    
    # Check CoT reasoning payload
    cot = res["cot_reasoning"]
    assert "entities" in cot
    assert len(cot["entities"]) == 3
    assert cot["entities"][0]["entity"] == "cat"
    assert cot["entities"][0]["attributes"] == ["blue"]
    
    # Check that optimized prompt contains explicit attribute bindings
    opt_prompt = res["optimized_prompt"]
    assert "blue" in opt_prompt
    assert "cat" in opt_prompt
    assert "yellow" in opt_prompt
    assert "box" in opt_prompt
    assert "red" in opt_prompt
    assert "bicycle" in opt_prompt
    
    # Check scene_graph field is JSON serializable
    dumped = json.dumps(res, indent=2)
    loaded = json.loads(dumped)
    assert loaded["cot_reasoning"]["entities"][0]["entity"] == "cat"
    assert loaded["scene_graph"]["entities"][0]["entity"] == "cat"


def test_optimize_edit_instruction_chatml():
    """Verify formatting of image editing instructions into official Qwen-VL ChatML template."""
    optimizer = PromptOptimizerAgent()
    
    # Standard single-image edit instruction
    raw_instr = "make the sky stormy and add dramatic lightning"
    chatml = optimizer.optimize_edit_instruction(raw_instr)
    
    assert "<|im_start|>system" in chatml
    assert OFFICIAL_CHATML_EDIT_SYSTEM_PROMPT in chatml
    assert "<|im_start|>user" in chatml
    assert "Picture 1: <|vision_start|><|image_pad|><|vision_end|>" in chatml
    assert raw_instr in chatml
    assert "<|im_end|>\n<|im_start|>assistant\n" in chatml
    
    # With reference summary
    chatml_ref = optimize_edit_instruction(
        instruction="change coat to bright yellow",
        reference_summary="A woman in a red coat standing in rain",
        num_images=1
    )
    assert "[Reference: A woman in a red coat standing in rain]" in chatml_ref
    assert "change coat to bright yellow" in chatml_ref
    
    # Multi-image edit instruction
    chatml_multi = optimize_edit_instruction(
        instruction="combine elements from both pictures",
        num_images=2
    )
    assert "Picture 1: <|vision_start|><|image_pad|><|vision_end|>" in chatml_multi
    assert "Picture 2: <|vision_start|><|image_pad|><|vision_end|>" in chatml_multi
    
    # Idempotency check: already-formatted ChatML prompt must not be double wrapped
    idempotent = optimize_edit_instruction(chatml)
    assert idempotent == chatml


def test_backward_compatibility_optimization_result():
    """Verify OptimizationResult supports dict indexing, attribute access, and API compatibility."""
    optimizer = PromptOptimizerAgent()
    
    res = optimizer.optimize_prompt(
        prompt="a cybernetic astronaut on Mars",
        style="cyberpunk",
        negative_prompt="grainy, noisy",
        custom_aspect_ratio="16:9"
    )
    
    # Dict indexing
    assert res["style_applied"] == "cyberpunk"
    assert res["recommended_aspect_ratio"] == "16:9"
    assert "cybernetic" in res["optimized_prompt"]
    assert "grainy, noisy" in res["negative_prompt"]
    
    # Attribute access
    assert res.style_applied == "cyberpunk"
    assert res.recommended_aspect_ratio == "16:9"
    assert res.recommended_steps == 15
    assert res.recommended_guidance == 7.5
    
    # Multi-turn context resolution
    chat_hist = [
        {"role": "user", "content": "a futuristic flying car over Tokyo"},
        {"role": "assistant", "content": "Generated image"},
        {"role": "user", "content": "now make it neon pink"}
    ]
    ctx_res = optimizer.optimize_with_context(
        raw_prompt="now make it neon pink",
        chat_history=chat_hist,
        style="cyberpunk"
    )
    assert ctx_res["had_context"] is True
    assert "futuristic flying car" in ctx_res["context_resolved_prompt"]
    assert "neon pink" in ctx_res["context_resolved_prompt"]


def test_compound_noun_handling():
    """Verify compound nouns are correctly parsed as single entities."""
    optimizer = PromptOptimizerAgent()
    prompt = "red sports car in front of modern glass skyscraper"
    
    sg = optimizer.decompose_scene(prompt)
    assert len(sg.entities) >= 2
    
    # First entity is compound noun "sports car" with attribute "red"
    e0 = sg.entities[0]
    assert e0.entity == "sports car"
    assert e0.attributes == ["red"]
    
    # Relation links sports car in front of skyscraper
    assert len(sg.relations) >= 1
    assert sg.relations[0].source == "sports car"
    assert sg.relations[0].preposition == "in front of"
