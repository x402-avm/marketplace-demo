import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, Union

STYLE_PRESETS: Dict[str, Dict[str, str]] = {
    "photorealistic": {
        "prefix": "A crisp photographic capture of",
        "suffix": "captured with natural diffuse lighting, accurate textures, and balanced composition on a 35mm lens at f/1.8, photorealistic clarity",
        "negative": "distorted anatomy, deformed limbs, blurry focus, artificial skin texture, low contrast, visual artifacts"
    },
    "cinematic_8k": {
        "prefix": "Cinematic film still of",
        "suffix": "captured in anamorphic widescreen format with volumetric lighting, subtle atmospheric depth, and cinematic color grading",
        "negative": "flat lighting, harsh oversaturation, noisy shadows, digital distortion, visual artifacts"
    },
    "anime_manga": {
        "prefix": "An anime-style digital illustration of",
        "suffix": "rendered with clear cel shading, crisp linework, expressive lighting, and atmospheric sky gradients",
        "negative": "photographic textures, muddy colors, deformed facial features, poorly drawn hands, visual artifacts"
    },
    "studio_portrait": {
        "prefix": "Professional studio portrait of",
        "suffix": "featuring Rembrandt lighting, shallow depth of field, sharp facial focus, and clean backdrop separation on an 85mm portrait lens",
        "negative": "harsh specular highlights, blurry eyes, distorted proportions, extra limbs, visual artifacts"
    },
    "cyberpunk": {
        "prefix": "Neon-drenched cyberpunk scene featuring",
        "suffix": "luminous neon signage, wet reflective streets, and intricate futuristic architectural details in a dusk atmosphere",
        "negative": "daylight, pastoral scenery, low contrast, washed out colors, visual artifacts"
    },
    "fantasy_oil": {
        "prefix": "Classical fantasy oil painting of",
        "suffix": "rendered with visible textured brushwork, rich tonal contrast, and dynamic chiaroscuro lighting",
        "negative": "digital CGI, smooth plastic textures, flat lighting, modern photographic elements, visual artifacts"
    },
    "minimalist_vector": {
        "prefix": "A modern minimalist graphic illustration of",
        "suffix": "featuring clean geometric silhouettes, harmonious negative space, and a curated color palette",
        "negative": "cluttered composition, photographic noise, complex textures, visual artifacts"
    },
    "analog_film": {
        "prefix": "A vintage analog photograph of",
        "suffix": "captured on 35mm film stock with subtle grain, natural color rendering, and gentle highlight roll-off",
        "negative": "harsh digital sharpening, extreme HDR, sterile plastic textures, visual artifacts"
    }
}

# Canonical spatial prepositions in descending order of pattern length
SPATIAL_PREPOSITION_PATTERNS: List[Tuple[str, str]] = [
    (r"\bon\s+top\s+of\b", "on top of"),
    (r"\bto\s+the\s+left\s+of\b", "to the left of"),
    (r"\bon\s+the\s+left\s+of\b", "to the left of"),
    (r"\bleft\s+of\b", "to the left of"),
    (r"\bto\s+the\s+right\s+of\b", "to the right of"),
    (r"\bon\s+the\s+right\s+of\b", "to the right of"),
    (r"\bright\s+of\b", "to the right of"),
    (r"\bin\s+front\s+of\b", "in front of"),
    (r"\bin\s+back\s+of\b", "behind"),
    (r"\bnext\s+to\b", "next to"),
    (r"\badjacent\s+to\b", "next to"),
    (r"\bclose\s+to\b", "next to"),
    (r"\bunderneath\s+of\b", "underneath"),
    (r"\bunderneath\b", "underneath"),
    (r"\bbeneath\b", "underneath"),
    (r"\bunder\b", "underneath"),
    (r"\bbelow\b", "underneath"),
    (r"\bbehind\b", "behind"),
    (r"\bbeside\b", "next to"),
    (r"\babove\b", "above"),
    (r"\bover\b", "above"),
    (r"\batop\b", "on top of"),
    (r"\bupon\b", "on top of"),
    (r"\bon\b", "on top of"),
    (r"\bby\b", "next to"),
    (r"\bbetween\b", "between"),
    (r"\binside\s+of\b", "inside"),
    (r"\binside\b", "inside"),
    (r"\bwithin\b", "inside"),
    (r"\boutside\s+of\b", "outside of"),
    (r"\boutside\b", "outside of"),
    (r"\baround\b", "around"),
    (r"\bsurrounding\b", "around")
]

CONVERSATIONAL_DELTA_PATTERNS: List[Tuple[str, str]] = [
    # 1. State / Environment / Time Shift: "now make it night", "make it sunset", "turn it into dusk", "set lighting to cinematic"
    (
        r'^(now\s+|also\s+|and\s+|then\s+)?(make\s+(it|them|this|the\s+scene|the\s+image|the\s+background|the\s+lighting)|turn\s+(it|this|the\s+scene|the\s+background)|transform\s+(it|this|the\s+scene)|set\s+(the\s+)?(time|lighting|weather|atmosphere|background)\s+to)\b',
        "environment_shift"
    ),
    # 2. Entity Attribute Modification: "change shirt to green", "switch background to beach", "paint walls blue", "recolor the car red"
    (
        r'^(now\s+|also\s+|and\s+|then\s+)?(change|switch|recolor|paint)\s+(the\s+|her\s+|his\s+|its\s+|their\s+)?([a-z0-9_-]+\s+)*(to|into)\b',
        "attribute_replacement"
    ),
    # 3. Direct Entity Property Assignment: "make her shirt green", "make the sky dark", "turn the car blue"
    (
        r'^(now\s+|also\s+|and\s+|then\s+)?(make|turn|paint)\s+(the\s+|her\s+|his\s+|its\s+|their\s+)?([a-z0-9_-]+)\s+([a-z0-9_-]+)\b',
        "attribute_replacement"
    ),
    # 4. Entity Addition: "add sunglasses", "insert a neon sign", "give him a hat", "put a cat on the table"
    (
        r'^(now\s+|also\s+|and\s+|then\s+)?(add|insert|include|give\s+(it|him|her|them)|put|place|introduce)\b',
        "entity_addition"
    ),
    # 5. Participial / Accessory Addition: "now with sunglasses", "and wearing a leather jacket", "holding a sword"
    (
        r'^(now\s+|also\s+|and\s+)?(with|wearing|holding|carrying|featuring)\s+([a-z0-9_-]+)',
        "entity_addition"
    ),
    # 6. Entity Removal / Exclusion: "remove sunglasses", "take off the hat", "without the car", "erase the crowd"
    (
        r'^(now\s+|also\s+|and\s+|then\s+)?(remove|delete|erase|take\s+(away|off)|drop)\b',
        "entity_removal"
    ),
    (
        r'\b(without\s+(the\s+|any\s+|his\s+|her\s+)?([a-z0-9_-]+))\b',
        "entity_removal"
    ),
    # 7. Entity Substitution: "replace dog with cat", "swap bicycle for sports car", "instead of dog, a cat"
    (
        r'^(now\s+|also\s+|and\s+|then\s+)?(replace|swap|substitute)\b',
        "entity_substitution"
    ),
    (
        r'\binstead\s+of\b',
        "entity_substitution"
    ),
    # 8. Relative / Scalar Adjustments: "more vibrant", "darker lighting", "closer zoom", "warmer tones"
    (
        r'^(now\s+|also\s+|and\s+)?(more|less|higher|lower|darker|brighter|warmer|cooler|closer|wider|sharper|softer)\b',
        "scalar_adjustment"
    ),
    # 9. Anaphoric Spatial Anchoring: "next to it", "on top of it", "behind it", "beside it"
    (
        r'\b(next\s+to\s+it|beside\s+it|on\s+top\s+of\s+it|behind\s+it|in\s+front\s+of\s+it|around\s+it|inside\s+it)\b',
        "spatial_addition"
    )
]

OFFICIAL_CHATML_EDIT_SYSTEM_PROMPT = (
    "<|im_start|>system\n"
    "Describe the key features of the input image (color, shape, size, texture, objects, background), "
    "then explain how the user's text instruction should alter or modify the image. "
    "Generate a new image that meets the user's requirements while maintaining consistency "
    "with the original input where appropriate.<|im_end|>\n"
)


@dataclass
class EntityAttribute:
    """Represents a discrete entity extracted from a scene with bound attributes."""
    entity: str
    attributes: List[str] = field(default_factory=list)
    spatial_role: str = "subject"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "attributes": list(self.attributes),
            "spatial_role": self.spatial_role
        }


@dataclass
class SpatialRelation:
    """Represents a directed spatial relationship between two scene entities."""
    source: str
    preposition: str
    target: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "preposition": self.preposition,
            "target": self.target
        }


@dataclass
class SceneGraph:
    """Structured representation of entities, attributes, relations, and reasoning trace."""
    entities: List[EntityAttribute] = field(default_factory=list)
    relations: List[SpatialRelation] = field(default_factory=list)
    thinking_trace: List[str] = field(default_factory=list)
    raw_prompt: str = ""
    synthesized_prompt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "thinking_trace": list(self.thinking_trace),
            "raw_prompt": self.raw_prompt,
            "synthesized_prompt": self.synthesized_prompt
        }


class OptimizationResult(dict):
    """Result dictionary supporting both dict indexing and attribute access."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


CONTROL_AND_VISION_TOKENS = re.compile(
    r"(?:Picture\s+\d+\s*:\s*)?<\|(?:im_start|im_end|vision_start|vision_end|image_pad|video_pad|box_start|box_end|ref_start|ref_end|quad_start|quad_end|fim_prefix|fim_middle|fim_suffix|endoftext)\|>",
    re.IGNORECASE
)
ANY_SPECIAL_TOKEN = re.compile(r"<\|.*?\|>", re.IGNORECASE)
ZERO_WIDTH_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")


def sanitize_chatml_input(text: str) -> str:
    """Recursively sanitize ChatML control and vision tokens to prevent nested reconstitution.
    
    Eliminates attacks such as '<|im_<|im_end|>end|>' and fake vision pad injections
    like 'Picture 2: <|vision_start|><|image_pad|><|vision_end|>'.
    """
    if not text:
        return ""
    cleaned = ZERO_WIDTH_PATTERN.sub("", text)
    passes = 0
    while CONTROL_AND_VISION_TOKENS.search(cleaned) and passes < 10:
        cleaned = CONTROL_AND_VISION_TOKENS.sub("", cleaned)
        passes += 1
    passes = 0
    while ANY_SPECIAL_TOKEN.search(cleaned) and passes < 10:
        cleaned = ANY_SPECIAL_TOKEN.sub("", cleaned)
        passes += 1
    return cleaned.strip()


def is_valid_preformatted_chatml(text: str) -> bool:
    """Validate whether text is a complete, authentic pre-formatted ChatML envelope.
    
    Prevents single-role injection shortcuts (e.g. '<|im_start|>user...') from bypassing
    system prompt and vision pad generation.
    """
    stripped = text.strip()
    if not stripped.startswith("<|im_start|>system"):
        return False
    if "<|im_start|>user" not in stripped:
        return False
    if "<|im_end|>" not in stripped:
        return False
    if "<|im_start|>assistant" not in stripped:
        return False
    return True


def optimize_edit_instruction(
    instruction: str,
    reference_summary: Optional[str] = None,
    num_images: int = 1
) -> str:
    """Format image editing instruction using the official Qwen-VL ChatML template."""
    clean_instr = (instruction or "").strip()

    # Preserve authentic pre-formatted ChatML without double-wrapping
    if is_valid_preformatted_chatml(clean_instr):
        return clean_instr if clean_instr.endswith("\n") else clean_instr + "\n"

    # Recursively sanitize control tokens and fake vision tags from instruction and reference
    clean_instr = sanitize_chatml_input(clean_instr)
    clean_ref = sanitize_chatml_input(reference_summary.strip()) if reference_summary else ""

    # Re-apply fallback if input was empty or consisted entirely of stripped control tokens
    if not clean_instr:
        clean_instr = "Modify the image according to user intent."

    vision_pad = "<|vision_start|><|image_pad|><|vision_end|>"
    img_refs_list = [f"Picture {i + 1}: {vision_pad}" for i in range(max(1, num_images))]
    img_refs = "\n".join(img_refs_list)

    if clean_ref:
        user_body = f"{img_refs}\n[Reference: {clean_ref}] {clean_instr}"
    else:
        user_body = f"{img_refs}\n{clean_instr}"

    return (
        f"{OFFICIAL_CHATML_EDIT_SYSTEM_PROMPT}"
        f"<|im_start|>user\n{user_body}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )


class PromptOptimizerAgent:
    """AI Engineer Agent: Enhances and optimizes prompts for image generation & editing.
    
    Features in-pipeline Chain-of-Thought (CoT) scene decomposition, spatial preposition
    mapping, adjective-noun binding isolation to prevent attribute bleeding, and official
    Qwen-VL ChatML instruction formatting.
    """

    def __init__(self):
        self.default_negative = (
            "distorted anatomy, deformed hands, missing fingers, extra digits, cropped framing, "
            "blurry focus, unnatural skin texture, visual artifacts, watermark, signature, username"
        )
        self._determiners = {"a", "an", "the", "this", "that", "these", "those", "some", "every", "each"}
        self._posture_verbs = {
            "sitting", "standing", "perched", "resting", "lying", "parked", "placed",
            "positioned", "situated", "located", "floating", "flying", "running", "walking", "sleeping"
        }
        self._auxiliary_verbs = {
            "is", "are", "was", "were", "be", "been", "being"
        }
        self._compound_nouns = {
            "sports car", "teddy bear", "coffee mug", "palm tree", "pine tree", "oak tree",
            "hot air balloon", "water bottle", "fire truck", "fighter jet"
        }
        self._known_colors = {
            "red", "green", "blue", "yellow", "black", "white", "orange", "purple",
            "pink", "brown", "gray", "grey", "cyan", "magenta", "violet", "indigo",
            "golden", "gold", "silver", "bronze", "copper", "crimson", "scarlet",
            "turquoise", "teal", "navy", "maroon", "amber", "emerald", "ruby",
            "beige", "tan", "lavender", "lilac", "olive", "coral", "peach",
            "dark", "light", "bright", "pale", "neon", "pastel", "vibrant", "vivid",
            "shiny", "matte", "glowing", "metallic"
        }
        self._known_descriptors = {
            "small", "little", "tiny", "mini", "miniature", "large", "big", "huge",
            "giant", "tall", "short", "long", "wide", "narrow", "thin", "thick",
            "wooden", "wood", "glass", "metal", "metallic", "stone", "plastic",
            "ceramic", "leather", "cotton", "silk", "wool", "paper", "cardboard",
            "fluffy", "furry", "smooth", "rough", "soft", "hard", "sharp",
            "round", "square", "rectangular", "circular", "oval", "triangular",
            "striped", "spotted", "checkered", "patterned", "textured",
            "ancient", "modern", "vintage", "antique", "futuristic", "cybernetic",
            "old", "young", "new", "fresh", "rusty", "broken", "dirty", "clean",
            "clear", "cloudy", "stormy", "sunny", "rainy", "snowy", "foggy",
            "happy", "sad", "angry", "calm", "serene", "fierce", "wild", "tame",
            "fast", "slow", "heavy"
        }
        self._known_adjectives = self._known_colors | self._known_descriptors

    def infer_aspect_ratio(self, prompt: str) -> str:
        """Infer best aspect ratio based on semantic subject."""
        p = prompt.lower()
        portrait_keywords = ["portrait", "girl", "boy", "man", "woman", "person", "model", "face", "standing", "character"]
        landscape_keywords = ["landscape", "mountain", "car", "vehicle", "cityscape", "scenery", "panorama", "horizon", "ocean", "wallpaper"]

        for word in portrait_keywords:
            if re.search(r'\b' + re.escape(word) + r'\b', p):
                return "9:16"
        for word in landscape_keywords:
            if re.search(r'\b' + re.escape(word) + r'\b', p):
                return "16:9"
        return "1:1"

    def _detect_delta(self, prompt: str) -> Tuple[bool, Optional[str]]:
        """Detect if prompt is a conversational delta instruction and return its category."""
        p_lower = prompt.strip().lower()
        for pattern, category in CONVERSATIONAL_DELTA_PATTERNS:
            if re.search(pattern, p_lower):
                return True, category
        return False, None

    def _extract_accumulated_prior_prompt(self, chat_history: Optional[list], current_prompt: str) -> Optional[str]:
        """Extract the true cumulative prompt of the previous turn from chat history."""
        if not chat_history:
            return None

        # Strategy 1: Check most recent assistant message with stored context_resolved_prompt
        for msg in reversed(chat_history):
            if isinstance(msg, dict) and msg.get("role") == "assistant" and isinstance(msg.get("metadata"), dict):
                resolved = msg["metadata"].get("context_resolved_prompt") or msg["metadata"].get("prompt_used")
                if resolved:
                    return resolved

        # Strategy 2: Sequential User Replay Accumulator
        user_prompts = []
        for msg in chat_history:
            if isinstance(msg, dict) and msg.get("role") == "user" and msg.get("content"):
                c = msg["content"].strip()
                if c and not c.startswith("Apply filter"):
                    user_prompts.append(c)

        if not user_prompts:
            return None

        # Exclude current prompt if already at the end of history
        if user_prompts[-1].lower() == current_prompt.strip().lower():
            user_prompts = user_prompts[:-1]

        if not user_prompts:
            return None

        # Accumulate sequentially
        cumulative = user_prompts[0]
        for p in user_prompts[1:]:
            is_d, d_type = self._detect_delta(p)
            if is_d and d_type:
                cumulative = self.apply_semantic_delta(cumulative, p, d_type)
            else:
                cumulative = p

        return cumulative

    def _resolve_attribute_replacement(self, prior_prompt: str, delta: str) -> str:
        """Replace target entity attribute in prior prompt to avoid conflicting token competition."""
        cleaned_delta = re.sub(r'^(now\s*,?\s*|also\s*,?\s*|and\s*,?\s*|then\s*,?\s*)', '', delta.strip(), flags=re.IGNORECASE).strip()
        m1 = re.search(r'(?:change|switch|recolor|paint)\s+(?:the\s+|her\s+|his\s+|their\s+|its\s+)?([a-z0-9_-]+)\s+(?:to|into)\s+([a-z0-9_\s-]+)', cleaned_delta, re.IGNORECASE)
        m2 = re.search(r'(?:make|turn|paint)\s+(?:the\s+|her\s+|his\s+|their\s+|its\s+)?([a-z0-9_-]+)\s+([a-z0-9_\s-]+)', cleaned_delta, re.IGNORECASE)

        match = m1 or m2
        if match:
            entity_noun = match.group(1).lower().strip()
            new_attr = match.group(2).lower().strip()

            if entity_noun in {"it", "this", "them", "image", "scene"}:
                return f"{prior_prompt}, {new_attr}"

            # Check if preceded by a known adjective (e.g. "red shirt" -> "green shirt")
            pattern_with_adj = re.compile(r'\b([a-z0-9_-]+)\s+((?:sports\s+|coffee\s+|teddy\s+)?' + re.escape(entity_noun) + r')\b', re.IGNORECASE)
            m_adj = pattern_with_adj.search(prior_prompt)
            if m_adj and m_adj.group(1).lower() in self._known_adjectives:
                full_noun = m_adj.group(2)
                return pattern_with_adj.sub(f"{new_attr} {full_noun}", prior_prompt, count=1)

            # Check if preceded by article (e.g. "a shirt" -> "a green shirt")
            pattern_art = re.compile(r'\b(a|an|the)\s+((?:sports\s+|coffee\s+|teddy\s+)?' + re.escape(entity_noun) + r')\b', re.IGNORECASE)
            m_art = pattern_art.search(prior_prompt)
            if m_art:
                full_noun = m_art.group(2)
                art = "an" if new_attr[:1] in "aeiou" else "a"
                return pattern_art.sub(f"{art} {new_attr} {full_noun}", prior_prompt, count=1)

            pattern_bare = re.compile(r'\b((?:sports\s+|coffee\s+|teddy\s+)?' + re.escape(entity_noun) + r')\b', re.IGNORECASE)
            if pattern_bare.search(prior_prompt):
                return pattern_bare.sub(lambda m: f"{new_attr} {m.group(1)}", prior_prompt, count=1)

            return f"{prior_prompt}, with {new_attr} {entity_noun}"

        return f"{prior_prompt}, {cleaned_delta}"

    def _resolve_environment_shift(self, prior_prompt: str, delta: str) -> str:
        """Resolve atmospheric or temporal shifts by removing contradictory lighting/time tokens."""
        cleaned_delta = re.sub(r'^(now\s*,?\s*|also\s*,?\s*|and\s*,?\s*|then\s*,?\s*)', '', delta.strip(), flags=re.IGNORECASE).strip()
        delta_core = re.sub(
            r'^(make\s+(it|them|this|the\s+scene|the\s+image|the\s+background|the\s+lighting)|turn\s+(it|this|the\s+scene|the\s+background)|transform\s+(it|this|the\s+scene)|set\s+(the\s+)?(time|lighting|weather|atmosphere|background)\s+to)\s+',
            '',
            cleaned_delta,
            flags=re.IGNORECASE
        ).strip()

        cleaned_prior = prior_prompt.strip()
        lower_delta = delta_core.lower()

        if any(w in lower_delta for w in ["night", "dusk", "twilight", "midnight", "evening", "dark"]):
            cleaned_prior = re.sub(
                r'\b(on\s+a\s+sunny\s+day|during\s+the\s+day|in\s+bright\s+daylight|sunny|sunlit|daytime|bright daylight|noon|morning sun|afternoon sun)\b',
                '',
                cleaned_prior,
                flags=re.IGNORECASE
            )
            cleaned_prior = re.sub(r'\s{2,}', ' ', cleaned_prior).strip(" ,.")
            if "at night" in lower_delta or lower_delta.startswith("night"):
                shift_text = delta_core if delta_core.startswith("at ") else f"at {delta_core}"
            else:
                shift_text = f"at night, {delta_core}" if "night" not in lower_delta else delta_core
            return f"{cleaned_prior}, {shift_text}"

        elif any(w in lower_delta for w in ["day", "daytime", "sunny", "sunlit", "morning", "noon"]):
            cleaned_prior = re.sub(
                r'\b(at\s+night|during\s+the\s+night|at\s+dusk|at\s+twilight|night|dusk|twilight|midnight|dark)\b',
                '',
                cleaned_prior,
                flags=re.IGNORECASE
            )
            cleaned_prior = re.sub(r'\s{2,}', ' ', cleaned_prior).strip(" ,.")
            shift_text = delta_core if ("during" in lower_delta or "in " in lower_delta) else f"in {delta_core}"
            return f"{cleaned_prior}, {shift_text}"

        else:
            return f"{cleaned_prior}, {delta_core}"

    def _resolve_entity_addition(self, prior_prompt: str, delta: str) -> str:
        """Bind added entity or wearable accessory without modifier bleeding into prior subjects."""
        cleaned_delta = re.sub(r'^(now\s*,?\s*|also\s*,?\s*|and\s*,?\s*|then\s*,?\s*)', '', delta.strip(), flags=re.IGNORECASE).strip()
        add_core = re.sub(
            r'^(add|insert|include|give\s+(it|him|her|them)|put|place|introduce|with|wearing|holding|carrying|featuring)\s+',
            '',
            cleaned_delta,
            flags=re.IGNORECASE
        ).strip()

        wearables = {
            "sunglasses", "glasses", "hat", "fedora", "cap", "jacket", "coat",
            "scarf", "backpack", "watch", "necklace", "mask", "gloves", "boots",
            "shoes", "helmet", "katana", "sword"
        }
        subjects = {
            "man", "woman", "person", "warrior", "astronaut", "detective", "girl",
            "boy", "model", "character", "figure", "robot", "dog", "cat"
        }

        has_subject = any(re.search(r'\b' + re.escape(s) + r'\b', prior_prompt, re.IGNORECASE) for s in subjects)
        is_wearable = any(w in add_core.lower() for w in wearables)

        if is_wearable and has_subject:
            if "holding" in cleaned_delta.lower():
                return f"{prior_prompt}, holding {add_core}"
            elif "sword" in add_core.lower() or "katana" in add_core.lower():
                art = "" if add_core.startswith(("a ", "an ", "the ")) else "a "
                return f"{prior_prompt}, with {art}{add_core}".replace("  ", " ")
            else:
                return f"{prior_prompt}, wearing {add_core}"
        else:
            prefix = "with " if not add_core.lower().startswith(("with ", "a ", "an ", "the ")) else ""
            return f"{prior_prompt}, {prefix}{add_core}".replace("  ", " ")

    def _resolve_entity_substitution(self, prior_prompt: str, delta: str) -> str:
        """Substitutes a source entity in prior prompt with a target entity."""
        cleaned_delta = re.sub(r'^(now\s*,?\s*|also\s*,?\s*|and\s*,?\s*|then\s*,?\s*)', '', delta.strip(), flags=re.IGNORECASE).strip()
        m = re.search(r'(?:replace|swap|substitute)\s+(?:the\s+)?([a-z0-9_\s-]+?)\s+(?:with|for|by)\s+([a-z0-9_\s-]+)', cleaned_delta, re.IGNORECASE)
        if not m:
            m = re.search(r'instead\s+of\s+(?:the\s+)?([a-z0-9_\s-]+?)[,\s]+(?:a\s+|an\s+|the\s+)?([a-z0-9_\s-]+)', cleaned_delta, re.IGNORECASE)

        if m:
            src = m.group(1).strip().lower()
            tgt = m.group(2).strip()

            if src in {"dog", "canine"} and re.search(r'\b(golden\s+retriever|retriever)\b', prior_prompt, re.IGNORECASE):
                return re.sub(r'\b(golden\s+retriever|retriever)\b', tgt, prior_prompt, count=1, flags=re.IGNORECASE)

            adj_src_pat = re.compile(r'\b([a-z0-9_-]+)\s+' + re.escape(src) + r'\b', re.IGNORECASE)
            m_adj = adj_src_pat.search(prior_prompt)
            if m_adj and m_adj.group(1).lower() in self._known_adjectives:
                return adj_src_pat.sub(tgt, prior_prompt, count=1)

            art_src_pat = re.compile(r'\b(a|an|the)\s+' + re.escape(src) + r'\b', re.IGNORECASE)
            if art_src_pat.search(prior_prompt):
                tgt_text = tgt if tgt.startswith(("a ", "an ", "the ")) else f"{'an' if tgt[:1].lower() in 'aeiou' else 'a'} {tgt}"
                return art_src_pat.sub(tgt_text, prior_prompt, count=1)

            return re.sub(r'\b' + re.escape(src) + r'\b', tgt, prior_prompt, count=1, flags=re.IGNORECASE)

        return f"{prior_prompt}, {cleaned_delta}"

    def _resolve_entity_removal(self, prior_prompt: str, delta: str) -> str:
        """Removes target entity and bound modifiers from prior prompt."""
        cleaned_delta = re.sub(r'^(now\s*,?\s*|also\s*,?\s*|and\s*,?\s*|then\s*,?\s*)', '', delta.strip(), flags=re.IGNORECASE).strip()
        m = re.search(r'(?:remove|delete|erase|take\s+(?:away|off)|without|drop)\s+(?:the\s+|any\s+|his\s+|her\s+|its\s+|a\s+|an\s+)?([a-z0-9_\s-]+)', cleaned_delta, re.IGNORECASE)
        if m:
            target = m.group(1).strip()
            pat = re.compile(r'(?:,\s*)?(?:wearing\s+|with\s+)?(?:a\s+|an\s+|the\s+)?(?:[a-z0-9_-]+\s+)?' + re.escape(target) + r'\b', re.IGNORECASE)
            cleaned = pat.sub('', prior_prompt)
            cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip(" ,.")
            return cleaned
        return prior_prompt

    def apply_semantic_delta(self, prior_prompt: str, raw_delta: str, delta_type: str) -> str:
        """Semantically merge a delta instruction into the prior prompt without attribute contradiction."""
        cleaned_delta = re.sub(r'^(now\s*,?\s*|also\s*,?\s*|and\s*,?\s*|then\s*,?\s*)', '', raw_delta.strip(), flags=re.IGNORECASE).strip()

        if delta_type == "attribute_replacement":
            return self._resolve_attribute_replacement(prior_prompt, cleaned_delta)
        elif delta_type == "environment_shift":
            return self._resolve_environment_shift(prior_prompt, cleaned_delta)
        elif delta_type == "entity_addition":
            return self._resolve_entity_addition(prior_prompt, cleaned_delta)
        elif delta_type == "entity_substitution":
            return self._resolve_entity_substitution(prior_prompt, cleaned_delta)
        elif delta_type == "entity_removal":
            return self._resolve_entity_removal(prior_prompt, cleaned_delta)
        else:
            return f"{prior_prompt}, {cleaned_delta}"

    def _generate_conversational_thinking_trace(
        self,
        raw_prompt: str,
        prior_prompt: str,
        resolved_prompt: str,
        delta_type: str
    ) -> List[str]:
        """Generate structured Chain-of-Thought reasoning steps for conversational delta resolution."""
        return [
            f"1. Conversational Delta Analysis: Identified intent type '{delta_type}' from input '{raw_prompt}'.",
            f"2. Context Retrieval: Preserved prior subject identity and spatial attributes from '{prior_prompt[:60]}...'.",
            f"3. Semantic Delta Execution: Applied non-contradictory {delta_type} modification isolating entity boundaries.",
            f"4. Prompt Synthesis: Emitted unified cohesive scene description: '{resolved_prompt[:80]}...'."
        ]

    def resolve_conversational_context(self, raw_prompt: str, chat_history: Optional[list] = None) -> str:
        """Merge conversational chat history context with current prompt when delta phrasing is detected."""
        if not chat_history or not raw_prompt:
            return raw_prompt.strip() if raw_prompt else ""

        p = raw_prompt.strip()
        is_delta, delta_type = self._detect_delta(p)
        if not is_delta:
            return p

        accumulated_prior = self._extract_accumulated_prior_prompt(chat_history, p)
        if not accumulated_prior:
            return p

        return self.apply_semantic_delta(accumulated_prior, p, delta_type or "general")

    def _parse_entity_segment(self, segment: str, spatial_role: str = "subject") -> EntityAttribute:
        """Parse a natural language segment into an EntityAttribute with bound attributes."""
        cleaned = re.sub(r'^[,\s\.]+|[,\s\.]+$', '', segment.strip())
        if not cleaned:
            return EntityAttribute(entity="element", attributes=[], spatial_role=spatial_role)

        # Check for descriptive relative clauses: "cat that is blue", "box which is yellow", "car painted red"
        rel_clause_match = re.search(
            r'\b(?:that\s+is|which\s+is|who\s+is|that\s+are|which\s+are|painted|colored)\s+(.+)$',
            cleaned,
            flags=re.IGNORECASE
        )
        if rel_clause_match:
            head_text = cleaned[:rel_clause_match.start()].strip()
            mod_text = rel_clause_match.group(1).strip()
            head_ea = self._parse_entity_segment(head_text, spatial_role=spatial_role)

            raw_mod_tokens = [t.strip(" ,.;:\"'!?") for t in mod_text.split() if t.strip(" ,.;:\"'!?")]
            mod_attributes = [
                t for t in raw_mod_tokens
                if t.lower() not in self._determiners
                and t.lower() not in {"and", "very", "strictly"}
                and t.lower() not in self._posture_verbs
                and t.lower() not in self._auxiliary_verbs
            ]
            combined_attributes = head_ea.attributes + [a for a in mod_attributes if a not in head_ea.attributes]
            return EntityAttribute(entity=head_ea.entity, attributes=combined_attributes, spatial_role=spatial_role)

        raw_tokens = cleaned.split()
        # Clean punctuation from every token
        tokens = [t.strip(" ,.;:\"'!?") for t in raw_tokens if t.strip(" ,.;:\"'!?")]

        # Strip leading determiners
        while tokens and tokens[0].lower() in self._determiners:
            tokens.pop(0)

        # Strip trailing posture and auxiliary verbs
        while len(tokens) > 1 and tokens[-1].lower() in (self._posture_verbs | self._auxiliary_verbs):
            tokens.pop()

        if not tokens:
            return EntityAttribute(entity="subject", attributes=[], spatial_role=spatial_role)

        # Handle post-positive adjectives (e.g. "cat blue" -> entity "cat", attribute "blue")
        post_attributes = []
        if any(t.lower() not in self._known_adjectives for t in tokens):
            while len(tokens) > 1 and tokens[-1].lower() in self._known_adjectives:
                post_attributes.insert(0, tokens.pop())

        # Check for recognized compound nouns
        if len(tokens) >= 2:
            potential_compound = f"{tokens[-2].lower()} {tokens[-1].lower()}"
            if potential_compound in self._compound_nouns:
                entity = potential_compound
                attributes = [t for t in tokens[:-2]] + post_attributes
                return EntityAttribute(entity=entity, attributes=attributes, spatial_role=spatial_role)

        entity = tokens[-1]
        attributes = [t for t in tokens[:-1]] + post_attributes
        return EntityAttribute(entity=entity, attributes=attributes, spatial_role=spatial_role)

    def _parse_segment_entities(self, segment: str, spatial_role: str = "subject") -> List[EntityAttribute]:
        """Parse a segment that may contain one or multiple conjoined entities (joined by 'and' or commas)."""
        cleaned = re.sub(r'^[,\s\.]+|[,\s\.]+$', '', segment.strip())
        if not cleaned:
            return []

        # Split on 'and' or commas to test for conjoined entities
        candidate_parts = [p.strip() for p in re.split(r'[,;]|\band\b', cleaned) if p.strip()]
        if len(candidate_parts) > 1:
            parsed_candidates = []
            for idx, part in enumerate(candidate_parts):
                role = spatial_role if idx == 0 else "co_subject" if spatial_role == "subject" else spatial_role
                ea = self._parse_entity_segment(part, spatial_role=role)
                parsed_candidates.append(ea)

            # Check if all candidate parts resolved to actual nouns (not adjectives/descriptors)
            all_are_nouns = all(
                ea.entity.lower() not in self._known_adjectives and ea.entity != "element" and ea.entity != "subject"
                for ea in parsed_candidates
            )
            if all_are_nouns:
                return parsed_candidates

        # Otherwise parse as single entity
        ea = self._parse_entity_segment(cleaned, spatial_role=spatial_role)
        return [ea]

    def decompose_scene(self, prompt: str) -> SceneGraph:
        """Decompose prompt into structured entity-attribute-relation tuples with CoT thinking trace."""
        cleaned = prompt.strip() if prompt else ""
        if not cleaned:
            default_entity = EntityAttribute(entity="composition", attributes=["abstract", "serene"], spatial_role="subject")
            return SceneGraph(
                entities=[default_entity],
                relations=[],
                thinking_trace=[
                    "1. Empty prompt detected; generated serene abstract baseline subject.",
                    "2. Bound default aesthetic attributes to ensure cohesive generation.",
                    "3. No spatial relations required for baseline abstract subject.",
                    "4. Synthesized fallback scene representation."
                ],
                raw_prompt="",
                synthesized_prompt="a serene abstract digital art composition"
            )

        # Detect spatial prepositions
        matches = []
        for pat, canonical in SPATIAL_PREPOSITION_PATTERNS:
            for m in re.finditer(pat, cleaned, flags=re.IGNORECASE):
                matches.append((m.start(), m.end(), canonical, m.group(0)))

        # Sort matches by start position; resolve overlaps by keeping earlier and longer match
        matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        non_overlapping = []
        last_end = 0
        for start, end, canonical, raw in matches:
            if start >= last_end:
                if non_overlapping:
                    prev_start, prev_end, prev_canonical, prev_raw = non_overlapping[-1]
                    intervening = cleaned[prev_end:start]
                    if not re.search(r'[a-zA-Z0-9]', intervening):
                        # Consecutive prepositions without intervening entity: collapse and extend
                        non_overlapping[-1] = (prev_start, end, prev_canonical, cleaned[prev_start:end])
                        last_end = end
                        continue
                non_overlapping.append((start, end, canonical, raw))
                last_end = end

        entities: List[EntityAttribute] = []
        relations: List[SpatialRelation] = []

        if not non_overlapping:
            # Single entity or comma/and separated without explicit spatial relations
            entities = self._parse_segment_entities(cleaned, spatial_role="subject")
            if not entities:
                entities.append(self._parse_entity_segment(cleaned, spatial_role="subject"))
        else:
            # Check if first preposition is leading (no substantive subject before it)
            first_start = non_overlapping[0][0]
            leading_text = cleaned[:first_start].strip()
            is_leading = not bool(re.search(r'[a-zA-Z0-9]', leading_text))

            if is_leading and len(non_overlapping) == 1:
                canonical_prep = non_overlapping[0][2]
                trailing_after_prep = cleaned[non_overlapping[0][1]:].strip()
                # Split fronted locative phrase: reference object before comma, subject after comma
                if "," in trailing_after_prep:
                    ref_part, subj_part = trailing_after_prep.split(",", 1)
                else:
                    parts = re.split(r'\s+(?=(?:a|an|the)\b)', trailing_after_prep)
                    if len(parts) >= 2:
                        ref_part = parts[0]
                        subj_part = " ".join(parts[1:])
                    else:
                        ref_part = trailing_after_prep
                        subj_part = ""

                ref_ea_list = self._parse_segment_entities(ref_part, spatial_role="reference_object")
                subj_ea_list = self._parse_segment_entities(subj_part, spatial_role="subject") if subj_part else []

                entities = [e for e in (subj_ea_list + ref_ea_list) if e.entity != "element"]
                if not entities:
                    entities = ref_ea_list

                if subj_ea_list and ref_ea_list:
                    for subj_e in subj_ea_list:
                        relations.append(SpatialRelation(
                            source=subj_e.entity,
                            preposition=canonical_prep,
                            target=ref_ea_list[0].entity
                        ))
            else:
                # Segment along prepositions
                segment_entities_list: List[List[EntityAttribute]] = []
                curr_pos = 0
                for idx, (start, end, canonical, raw) in enumerate(non_overlapping):
                    segment_text = cleaned[curr_pos:start]
                    role = "subject" if idx == 0 else "reference_object"
                    eas = self._parse_segment_entities(segment_text, spatial_role=role)
                    segment_entities_list.append(eas)
                    curr_pos = end

                # Final trailing segment
                trailing_text = cleaned[curr_pos:]
                final_prep = non_overlapping[-1][2]
                role = "support" if final_prep in ("on top of", "above") else "reference_object"
                trailing_eas = self._parse_segment_entities(trailing_text, spatial_role=role)
                segment_entities_list.append(trailing_eas)

                # Flatten entities while preserving order
                for eas in segment_entities_list:
                    for ea in eas:
                        if ea.entity != "element":
                            entities.append(ea)

                # Construct directed spatial relations between adjacent segments
                for idx, (start, end, canonical, raw) in enumerate(non_overlapping):
                    src_eas = segment_entities_list[idx]
                    tgt_eas = segment_entities_list[idx + 1]
                    if src_eas and tgt_eas:
                        for src_e in src_eas:
                            relations.append(SpatialRelation(
                                source=src_e.entity,
                                preposition=canonical,
                                target=tgt_eas[0].entity
                            ))

        # Build Thinking Trace
        bindings_list = [f"{e.entity} [{', '.join(e.attributes) if e.attributes else 'none'}]" for e in entities]
        bindings_summary = ", ".join(bindings_list)

        isolated_bindings = [
            f"'{', '.join(e.attributes)}' bound exclusively to '{e.entity}'"
            for e in entities if e.attributes
        ]
        isolated_summary = "; ".join(isolated_bindings) if isolated_bindings else "no bound modifiers"

        relations_list = [f"'{r.source}' {r.preposition} '{r.target}'" for r in relations]
        relations_summary = ", ".join(relations_list) if relations_list else "no inter-entity spatial edges"

        entity_noun = "entity" if len(entities) == 1 else "entities"
        thinking_trace = [
            f"1. Decomposed scene into {len(entities)} discrete {entity_noun} with explicit attribute bindings: {bindings_summary}.",
            f"2. Verified adjective-noun isolation to prevent cross-attribute color bleeding: {isolated_summary}.",
            f"3. Established spatial relationship graph: {relations_summary}.",
            "4. Synthesized cohesive natural language scene description enforcing spatial layout and semantic attribute boundaries without legacy boilerplate."
        ]

        # Synthesize dense prompt avoiding attribute bleeding
        def get_desc(ent_name: str) -> str:
            e = next((x for x in entities if x.entity == ent_name), None)
            if e and e.attributes:
                return f"{' '.join(e.attributes)} {e.entity}".strip()
            return ent_name

        bound_clauses = []
        for e in entities:
            if e.attributes:
                attrs = ", ".join(e.attributes)
                bound_clauses.append(f"the {attrs} characteristics belong strictly to the {e.entity}")

        isolation_str = ""
        if bound_clauses and len(entities) >= 2:
            isolation_str = (
                "Each element maintains strict semantic boundaries without cross-attribute bleeding: " +
                ", ".join(bound_clauses) +
                ", maintaining crisp spatial separation."
            )

        if relations and len(entities) >= 2:
            synthesized_parts = []
            first_rel = relations[0]
            subj_desc = get_desc(first_rel.source)
            tgt_0_desc = get_desc(first_rel.target)
            tgt_art = "an" if tgt_0_desc.lower()[:1] in ("a", "e", "i", "o", "u") else "a"

            synthesized_parts.append(
                f"A clearly structured scene featuring a {subj_desc} positioned {first_rel.preposition} {tgt_art} {tgt_0_desc}."
            )

            # Subsequent relations: construct "The {curr_rel.source} is positioned {curr_rel.preposition} a {curr_tgt_desc}."
            for rel_idx in range(1, len(relations)):
                curr_rel = relations[rel_idx]
                curr_tgt_desc = get_desc(curr_rel.target)
                art = "an" if curr_tgt_desc.lower()[:1] in ("a", "e", "i", "o", "u") else "a"
                synthesized_parts.append(
                    f"The {curr_rel.source} is positioned {curr_rel.preposition} {art} {curr_tgt_desc}."
                )

            if isolation_str:
                synthesized_parts.append(isolation_str)

            synthesized_prompt = " ".join(synthesized_parts)
        elif len(entities) >= 2 and isolation_str:
            # Multi-entity prompt without explicit spatial relations (e.g. conjoined entities)
            entity_descs = [get_desc(e.entity) for e in entities]
            if len(entity_descs) == 2:
                comp_intro = f"A clearly structured scene featuring a {entity_descs[0]} alongside a {entity_descs[1]}."
            else:
                comp_intro = f"A clearly structured scene featuring {', '.join(entity_descs[:-1])}, and {entity_descs[-1]}."
            synthesized_prompt = f"{comp_intro} {isolation_str}"
        else:
            synthesized_prompt = cleaned

        return SceneGraph(
            entities=entities,
            relations=relations,
            thinking_trace=thinking_trace,
            raw_prompt=cleaned,
            synthesized_prompt=synthesized_prompt
        )

    def optimize_edit_instruction(
        self,
        instruction: str,
        reference_summary: Optional[str] = None,
        num_images: int = 1
    ) -> str:
        """Format image editing instruction using official Qwen-VL ChatML template."""
        return optimize_edit_instruction(
            instruction=instruction,
            reference_summary=reference_summary,
            num_images=num_images
        )

    def optimize_edit_with_reasoning(
        self,
        instruction: str,
        parent_prompt: Optional[str] = None,
        image_context: Optional[Union[str, List[str], Any]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        num_images: int = 1,
        negative_prompt: Optional[str] = None,
        enable_cot: bool = True
    ) -> OptimizationResult:
        """Execute Chain-of-Thought reasoning for Single I2I and Multi-I2I image editing.

        Decomposes user edit instruction, resolves conversational delta phrasing against
        prior turn context, isolates entity-attribute bindings to prevent modifier bleeding
        into preserved subject areas, generates explicit preservation notes, and compiles
        into the official Qwen-VL ChatML instruction format.
        """
        clean_instr = (instruction or "").strip()
        if not clean_instr:
            clean_instr = "Modify the image according to user intent."

        # Determine effective number of reference images
        effective_num_images = num_images
        if isinstance(image_context, list):
            effective_num_images = max(effective_num_images, len(image_context))
        effective_num_images = max(1, effective_num_images)

        # 1. Multi-turn conversational delta resolution
        resolved_instruction = self.resolve_conversational_context(clean_instr, chat_history)
        if resolved_instruction == clean_instr and parent_prompt:
            p_lower = clean_instr.lower()
            delta_prefix = any(p_lower.startswith(w) for w in ["now", "also", "and", "then", "make", "add", "change"])
            if delta_prefix:
                resolved_instruction = f"{parent_prompt}, {clean_instr}"

        had_context = bool(resolved_instruction != clean_instr or (chat_history and len(chat_history) > 0))

        # 2. Classify editing intent
        instr_lower = resolved_instruction.lower()
        if effective_num_images > 1:
            intent_name = "multi_image_composition"
        elif any(w in instr_lower for w in ["add", "insert", "put", "place", "give", "attach"]):
            intent_name = "element_addition"
        elif any(w in instr_lower for w in ["remove", "delete", "erase", "take off", "without"]):
            intent_name = "element_removal"
        elif any(w in instr_lower for w in ["night", "day", "sunset", "sunrise", "lighting", "weather", "rain", "snow", "fog", "background", "sky"]):
            intent_name = "global_style_environment"
        else:
            intent_name = "attribute_modification"

        # 3. Derive preservation boundaries
        if effective_num_images > 1:
            preservation_notes = (
                f"Preserving primary subject geometry and facial identity from Picture 1; "
                f"composing background environment, lighting, and style cues from Picture 2 "
                f"across {effective_num_images} conditioned inputs."
            )
        elif intent_name == "element_addition":
            preservation_notes = "Preserving original subject geometry, pose, facial identity, and unedited background regions; localizing new element addition."
        elif intent_name == "element_removal":
            preservation_notes = "Preserving surrounding background coherence, texture continuity, and unedited subject features; inpainting removed region."
        elif intent_name == "global_style_environment":
            preservation_notes = "Preserving foreground subject identity, geometry, and placement; adapting ambient illumination, reflections, and atmospheric depth."
        else:
            preservation_notes = "Preserving overall composition, spatial geometry, and unedited subject features; strictly isolating attribute modification."

        # 4. Extract entity-attribute bindings for edited elements
        edit_entities = self._parse_segment_entities(clean_instr, spatial_role="edit_target")
        edit_bound_clauses = []
        for e in edit_entities:
            if e.attributes:
                attrs = ", ".join(e.attributes)
                edit_bound_clauses.append(f"the {attrs} characteristics belong strictly to the {e.entity}")

        if edit_bound_clauses:
            isolation_summary = (
                f"'{', '.join(edit_bound_clauses)}' bound strictly without cross-attribute bleeding into preserved image regions"
            )
        else:
            isolation_summary = "no conflicting color or texture modifiers introduced"

        # 5. Build 4-step Chain-of-Thought Thinking Trace
        thinking_trace = [
            f"1. Analyzed editing intent ({intent_name}) and resolved conversational context: '{resolved_instruction}'.",
            f"2. Verified adjective-noun isolation to prevent cross-attribute modifier bleeding: {isolation_summary}.",
            f"3. Established spatial and compositional preservation boundaries: {preservation_notes}.",
            "4. Synthesized cohesive ChatML visual instruction enforcing explicit modification goals and semantic preservation boundaries."
        ]

        # 6. Format ChatML edit instruction with reference preservation summary
        ref_context = f"[Preserve: {preservation_notes}]"
        if parent_prompt:
            ref_context = f"[Reference: {parent_prompt} | Preserve: {preservation_notes}]"

        chatml_prompt = optimize_edit_instruction(
            instruction=resolved_instruction,
            reference_summary=ref_context,
            num_images=effective_num_images
        )

        combined_negative = "distorted anatomy, deformed limbs, blurry focus, artificial skin texture, low contrast, visual artifacts"
        if negative_prompt and negative_prompt.strip():
            combined_negative = f"{negative_prompt.strip()}, {combined_negative}"

        cot_payload = {
            "intent": intent_name,
            "preservation_notes": preservation_notes,
            "thinking_trace": thinking_trace,
            "resolved_instruction": resolved_instruction,
            "entities": [e.to_dict() for e in edit_entities],
            "num_images": effective_num_images,
            "had_context": had_context
        }

        return OptimizationResult({
            "original_prompt": clean_instr,
            "optimized_prompt": chatml_prompt,
            "negative_prompt": combined_negative,
            "thinking_trace": thinking_trace,
            "preservation_notes": preservation_notes,
            "cot_reasoning": cot_payload,
            "scene_graph": {
                "entities": [e.to_dict() for e in edit_entities],
                "relations": [],
                "thinking_trace": thinking_trace,
                "raw_prompt": clean_instr,
                "synthesized_prompt": resolved_instruction
            },
            "had_context": had_context,
            "num_images": effective_num_images,
            "explanation": f"Editing instruction compiled with CoT intent reasoning ({intent_name}) and ChatML formatting."
        })

    def optimize_prompt(
        self,
        prompt: str,
        style: Optional[str] = "photorealistic",
        negative_prompt: Optional[str] = None,
        custom_aspect_ratio: Optional[str] = None,
        enable_cot: bool = True
    ) -> OptimizationResult:
        """Alias for optimize() returning structured OptimizationResult."""
        return self.optimize(
            raw_prompt=prompt,
            style=style,
            negative_prompt=negative_prompt,
            custom_aspect_ratio=custom_aspect_ratio,
            enable_cot=enable_cot
        )

    def optimize_with_context(
        self,
        raw_prompt: str,
        chat_history: Optional[list] = None,
        style: Optional[str] = "photorealistic",
        negative_prompt: Optional[str] = None,
        custom_aspect_ratio: Optional[str] = None,
        enable_cot: bool = True
    ) -> OptimizationResult:
        """Context-aware prompt optimization leveraging multi-turn chat history."""
        contextual_prompt = self.resolve_conversational_context(raw_prompt, chat_history)
        result = self.optimize(
            raw_prompt=contextual_prompt,
            style=style,
            negative_prompt=negative_prompt,
            custom_aspect_ratio=custom_aspect_ratio,
            enable_cot=enable_cot
        )
        result["raw_input_prompt"] = raw_prompt
        result["context_resolved_prompt"] = contextual_prompt
        result["had_context"] = bool(chat_history and len(chat_history) > 0)
        return result

    def optimize(
        self,
        raw_prompt: str,
        style: Optional[str] = "photorealistic",
        negative_prompt: Optional[str] = None,
        custom_aspect_ratio: Optional[str] = None,
        enable_cot: bool = True
    ) -> OptimizationResult:
        """Optimize prompt with Chain-of-Thought decomposition, stylistic enhancement, and CPU-tuned parameters."""
        cleaned_prompt = raw_prompt.strip() if raw_prompt else "a serene abstract digital art composition"

        selected_style = (style or "photorealistic").lower()
        preset = STYLE_PRESETS.get(selected_style, STYLE_PRESETS["photorealistic"])

        scene_graph = self.decompose_scene(cleaned_prompt) if enable_cot else None

        # Build enriched prompt
        if enable_cot and scene_graph and scene_graph.synthesized_prompt and scene_graph.synthesized_prompt != cleaned_prompt:
            # Use synthesized prompt with explicit spatial binding and anti-bleeding
            core_content = scene_graph.synthesized_prompt
            enhanced_prompt = f"{preset['prefix']} {core_content}, {preset['suffix']}".strip()
        else:
            enhanced_prompt = f"{preset['prefix']} {cleaned_prompt}, {preset['suffix']}".strip()

        # Build comprehensive negative prompt
        combined_negative = preset["negative"]
        if negative_prompt and negative_prompt.strip():
            combined_negative = f"{negative_prompt.strip()}, {combined_negative}"

        aspect_ratio = (
            custom_aspect_ratio
            if custom_aspect_ratio in ("1:1", "16:9", "9:16", "4:3", "3:2")
            else self.infer_aspect_ratio(cleaned_prompt)
        )

        recommended_steps = 15
        recommended_guidance = 7.5

        thinking_trace = scene_graph.thinking_trace if scene_graph else []
        cot_payload = {
            "entities": [e.to_dict() for e in scene_graph.entities] if scene_graph else [],
            "relations": [r.to_dict() for r in scene_graph.relations] if scene_graph else [],
            "thinking_trace": thinking_trace,
            "raw_prompt": scene_graph.raw_prompt if scene_graph else cleaned_prompt,
            "synthesized_prompt": scene_graph.synthesized_prompt if scene_graph else cleaned_prompt
        }

        return OptimizationResult({
            "original_prompt": cleaned_prompt,
            "optimized_prompt": enhanced_prompt,
            "negative_prompt": combined_negative,
            "style_applied": selected_style,
            "recommended_steps": recommended_steps,
            "recommended_guidance": recommended_guidance,
            "recommended_aspect_ratio": aspect_ratio,
            "thinking_trace": thinking_trace,
            "cot_reasoning": cot_payload,
            "scene_graph": scene_graph.to_dict() if scene_graph else None,
            "explanation": (
                f"Prompt synthesized using in-pipeline Chain-of-Thought spatial reasoning and '{selected_style}' aesthetic; "
                "adjective-noun bindings isolated to prevent attribute bleeding; negative prompt configured without obsolete boilerplate."
            )
        })
