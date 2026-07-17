import random
import json
import db

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
    def generate_dj_commentary(track_title=""):
        commentary = random.choice(AI_DJ_COMMENTARIES)
        if track_title:
            commentary += f" Featuring '{track_title}'."
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
