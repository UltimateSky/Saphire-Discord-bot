from dotenv import load_dotenv
import os
load_dotenv()

# Test Spotify
try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=os.getenv('SPOTIFY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
    ))
    result = sp.search(q='Never Gonna Give You Up', limit=1, type='track')
    track = result['tracks']['items'][0]
    name = track['name']
    artist = track['artists'][0]['name']
    print(f'Spotify OK: Found -> {name} by {artist}')
except Exception as e:
    print(f'Spotify ERROR: {e}')

# Test Genius
try:
    import lyricsgenius
    genius = lyricsgenius.Genius(os.getenv('GENIUS_API_TOKEN'), verbose=False, timeout=10)
    song = genius.search_song('Bohemian Rhapsody', 'Queen')
    if song:
        print(f'Genius OK: Found -> {song.title} by {song.artist}')
    else:
        print('Genius OK (token valid but no result)')
except Exception as e:
    print(f'Genius ERROR: {e}')
