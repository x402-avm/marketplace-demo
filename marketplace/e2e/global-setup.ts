export default async function globalSetup() {
  const token = 'a'.repeat(64);

  // 1. Check Algod :4001 health
  try {
    const algodRes = await fetch('http://localhost:4001/health', {
      headers: { 'X-Algo-API-Token': token },
    });
    if (!algodRes.ok) {
      throw new Error(`Algod health check returned HTTP ${algodRes.status} ${algodRes.statusText}`);
    }
  } catch (err: any) {
    throw new Error(
      `Algod is not healthy at http://localhost:4001. Ensure LocalNet is running. Error: ${err.message}`
    );
  }

  // 2. Check Gateway :8800 /api/health
  try {
    const gatewayRes = await fetch('http://localhost:8800/api/health');
    if (!gatewayRes.ok) {
      throw new Error(`Gateway health check returned HTTP ${gatewayRes.status} ${gatewayRes.statusText}`);
    }
    const body = await gatewayRes.json();
    if (!body || body.ok !== true) {
      throw new Error(`Gateway health response invalid: ${JSON.stringify(body)}`);
    }
  } catch (err: any) {
    throw new Error(
      `Gateway is not healthy at http://localhost:8800/api/health. Ensure marketplace/gateway is running. Error: ${err.message}`
    );
  }

  console.log('[global-setup] Algod :4001 and Gateway :8800 are both healthy.');

  // Give runtime models (e.g. Kokoro ONNX) a moment to finish CPU initialization
  await new Promise((r) => setTimeout(r, 3000));

  // 3. Warm up running MCP proxies so tool cache in gateway is populated
  const warmListings = ['tts-1', 'tts-2', 'tts-3', 'tts-4', 'sandbox_mcp-1'];
  for (const lid of warmListings) {
    for (let attempt = 1; attempt <= 6; attempt++) {
      try {
        const res = await fetch(`http://localhost:8800/api/listings/${lid}`);
        if (res.ok) {
          const data = await res.json();
          if (data.tools && data.tools.length > 0) {
            console.log(`[global-setup] Warmed up ${lid}: ${data.tools[0].name} (${data.tools[0].price})`);
            break;
          }
        }
      } catch {
        // retry
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
}
