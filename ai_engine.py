import random
import json
import db
import os
import asyncio

MOOD_PALETTES = {
    'chill': ['lofi hip hop', 'acoustic chill', 'ambient lounge', 'slow beats'],
    'energetic': ['workout phonk', 'edm party', 'high tempo dance', 'rock anthems'],
    'focus': ['synthwave study', 'piano instrumental', 'deep focus beats'],
    'party': ['top 40 hits', 'dance pop', 'latin club', 'hip hop party']
}

AI_DJ_COMMENTARIES = [
    "You're tuned into AuraSound 2032! Up next, we got an absolute banger for you...",
    "Keeping the vibe alive in Vishnu's room. Check out this smooth transition...",
    "AI DJ here! Based on what you've been listening to, I picked this track just for you...",
    "Turn up the volume! Here comes another hit on AuraSound."
]

class AIEngine:
    @staticmethod
    async def generate_dj_commentary(track_title="", mood="chill", history=None):
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                
                history_titles = [t.get('title', '') for t in history if isinstance(t, dict)] if history else []
                history_text = ", ".join(history_titles[:3]) if history_titles else "some cool beats"
                prompt = (
                    f"You are the vibrant AI radio DJ for AuraSound 2032. "
                    f"The user is currently listening to '{track_title}'. "
                    f"Their mood is '{mood}'. They recently listened to: {history_text}. "
                    f"Give a short, punchy, energetic, 1-2 sentence DJ introduction for this track. "
                    f"Do not use quotes or sound robotic. Speak directly to the listener as a cool radio host."
                )
                
                # google.genai has async methods via client.aio, but for simplicity we run sync in executor
                loop = asyncio.get_running_loop()
                def fetch():
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                    )
                    return response.text.strip()
                
                commentary = await loop.run_in_executor(None, fetch)
                return commentary
            except Exception as e:
                print(f"[AI DJ Error] {e}")
        
        # Fallback if no API key or API fails
        commentary = random.choice(AI_DJ_COMMENTARIES)
        if track_title:
            commentary = f"You're tuned into AuraSound! Up next, we got an absolute banger: '{track_title}'."
        return commentary
    @staticmethod
    async def get_smart_recommendations(user_id: int, mood: str = "chill", current_track: dict = None):
        history = await db.get_liked_songs(user_id) if user_id else []
        
        # Determine search keywords
        keywords = MOOD_PALETTES.get(mood.lower(), MOOD_PALETTES['chill'])
        selected_query = random.choice(keywords)
        
        if current_track and current_track.get('title'):
            # Mix current track artist into recommendations
            words = current_track['title'].split()
            if len(words) > 0:
                selected_query = f"{words[0]} type track"

        cache_key = f"rec:{mood}:{selected_query}"
        cached = await db.get_cached_search(cache_key)
        if cached:
            return cached

        # Perform REAL live search for mood query
        import asyncio
        from server import multi_source_search
        loop = asyncio.get_running_loop()
        recommendations = await loop.run_in_executor(None, multi_source_search, selected_query, 'all', 6)
        
        if recommendations:
            await db.set_cached_search(cache_key, recommendations)
        return recommendations
