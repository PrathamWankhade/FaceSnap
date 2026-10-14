import { NextRequest, NextResponse } from 'next/server';

const GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions';
const SYSTEM_PROMPT =
  'You are a helpful assistant for the FaceSnap student registration and verification system. Keep answers concise and friendly.';

// Simple in-memory rate limit (per instance): 20 requests / minute / IP.
const hits = new Map<string, { count: number; reset: number }>();
const WINDOW_MS = 60_000;
const MAX_HITS = 20;

const MODEL_ALLOWLIST = new Set([
  'llama-3.3-70b-versatile',
  'llama-3.1-70b-versatile',
  'llama-3.1-8b-instant',
  'llama-3.2-3b-preview',
  'mixtral-8x7b-32768',
  'gemma2-9b-it',
]);

export async function POST(req: NextRequest) {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: 'Chat service not configured.' }, { status: 503 });
  }

  const ip = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || 'unknown';
  const now = Date.now();
  const entry = hits.get(ip);
  if (!entry || now > entry.reset) {
    hits.set(ip, { count: 1, reset: now + WINDOW_MS });
  } else {
    entry.count += 1;
    if (entry.count > MAX_HITS) {
      return NextResponse.json({ error: 'Rate limit exceeded. Try again later.' }, { status: 429 });
    }
  }

  let body: { messages?: Array<{ role: string; content: string }>; model?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON.' }, { status: 400 });
  }

  const messages = (body.messages || []).slice(-20).map((m) => ({
    role: m.role === 'user' ? 'user' : 'assistant',
    content: String(m.content || '').slice(0, 2000),
  }));
  if (!messages.length || !messages.some((m) => m.role === 'user')) {
    return NextResponse.json({ error: 'No user message provided.' }, { status: 400 });
  }

  const requested = String(body.model || process.env.AI_MODEL || 'llama-3.3-70b-versatile');
  const model = MODEL_ALLOWLIST.has(requested) ? requested : 'llama-3.3-70b-versatile';

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 25_000);
  try {
    const response = await fetch(GROQ_API_URL, {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        messages: [{ role: 'system', content: SYSTEM_PROMPT }, ...messages],
        temperature: 0.7,
        max_tokens: 1024,
      }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const text = await response.text().catch(() => '');
      return NextResponse.json(
        { error: response.status === 401 || response.status === 403 ? 'Chat provider rejected the request.' : `Provider error (${response.status}).`, detail: text.slice(0, 500) },
        { status: 502 }
      );
    }
    const data = await response.json();
    const reply = data.choices?.[0]?.message?.content || 'Sorry, I could not process that.';
    return NextResponse.json({ reply: String(reply).slice(0, 4000) });
  } catch (e) {
    const msg = e instanceof Error && e.name === 'AbortError' ? 'Chat request timed out.' : 'Chat request failed.';
    return NextResponse.json({ error: msg }, { status: 502 });
  } finally {
    clearTimeout(timeout);
  }
}
