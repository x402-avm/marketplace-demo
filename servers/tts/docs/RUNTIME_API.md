# TTS Runtime API

The Central Runtime server provides a standard HTTP interface for TTS generation.

## Endpoint: `POST /tts`

### Request Body (JSON)
| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `text` | string | Yes | - | The input text to synthesize (max 1000 chars) |
| `voice` | string | No | `af_heart` | Voice ID for Kokoro |
| `speed` | float | No | `1.0` | Speech speed multiplier |

### Response
- **Success (200)**: Returns `audio/wav` byte stream.
- **Error (400)**: Returns string message if text exceeds strict limits.

### Memory Optimizations
The endpoint aggressively calls python's `gc.collect()` and manually `del`etes large text and audio byte arrays immediately after generation to ensure consistent memory overhead over long uptimes.
