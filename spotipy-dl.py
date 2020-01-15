from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

import spotipy
from spotipy import util, client
from spotipy.oauth2 import SpotifyClientCredentials

import youtube_dl

import json
from json.decoder import JSONDecodeError

import unicodedata
import re
import os



# =========== Credentials ===========

# YouTube API
DEVELOPER_KEY = ""
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Spotify API
client_id = ""
client_secret = ""
redirect_url = "https://google.com"

username = ""
scope = 'playlist-read-private'

# =========== search test ===========


playlist_uri = "spotify:playlist:5aBb1HzhbDkSDUP7kWAi2g"

# =========== Util ===========

def normalize_unicodes(text):
    if re.findall(u"[^\u0000-\u007e]+", text):
        return (unicodedata.normalize('NFKD', text).encode('ascii', 'ignore')).decode('utf8')
    else:
        return text

def resume_tracks_info(tracks):
    track_info = []
    for t in tracks:
        track = {}
        track['name'] = normalize_unicodes(t['track']['name'])
        track['artist'] = normalize_unicodes(t['track']['artists'][0]['name'])
        track['duration'] =  t['track']['duration_ms']
        track_info.append(track)

    return track_info

def to_milissec(yt_duration):
    d_h = 0
    d_min = 0
    d_sec = 0
    if ('H' in yt_duration):
        dur = yt_duration[2:].split('H')
        d_h = int(dur[0])
        if('M' in dur[1]):
            dur2 = dur[1].split('M')
            d_min = int(dur2[0])
            if('S' in dur2[1]):
                d_sec = int(dur2[1][:-1])
        
    else:
        if ('M' in yt_duration):
            dur = yt_duration[2:].split('M')
            d_min = int(dur[0])
            if('S' in dur[1]):
                d_sec = int(dur[1][:-1])
        else:
            d_sec = int(yt_duration[2:-1])            
        
    return (d_h * 3600000) + (d_min * 60000) + (d_sec * 1000)

def youtube_search(query, max_results):
    yout = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                    developerKey=DEVELOPER_KEY)

    search_response = yout.search().list(
        q=query,
        part='id,snippet',
        maxResults=max_results
    ).execute()

    videos = []
    
    for search_result in search_response.get('items', []):
        if search_result['id']['kind'] == 'youtube#video':
            video_id = search_result['id']['videoId']
            request = yout.videos().list(
                part="contentDetails",
                id=video_id,
                fields="items"
            ).execute()

            duration = request['items'][0]['contentDetails']['duration']
            definition = request['items'][0]['contentDetails']['definition']
            
            v = {}
            v['title'] = search_result['snippet']['title']
            v['id'] = video_id
            v['duration'] = to_milissec(duration)
            v['definition'] = definition

            videos.append(v)

    return videos

def min_time_diff(track_time, videos):
    difs = []
    for v in videos:
        difs.append((str(v['id']), abs(track_time - int(v['duration']))))

    return min(difs,key=lambda item:item[1])
    
def get_playlist_id(link):
    return str(link.split(":")[2])

def print_json(text):
    print(json.dumps(text, sort_keys=True, indent=4))

# =========== Execution ===========

max_videos_result = 10

# Erase cache and prompt for user permission
try:
    token = util.prompt_for_user_token(
        username, scope, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_url)
except (AttributeError, JSONDecodeError):
    os.remove(f".cache-{username}")
    token = util.prompt_for_user_token(
        username, scope, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_url)

client_credentials_manager = SpotifyClientCredentials(
    client_id=client_id, client_secret=client_secret)
spotifyObject = client.Spotify(
    auth=token, client_credentials_manager=client_credentials_manager)

print("Capturando informações da playlist...")

playlist_id = get_playlist_id(playlist_uri)
playlist_info = spotifyObject.playlist_information(playlist_id, "name")
playlist_name = normalize_unicodes(playlist_info['name'])

all_track_info = spotifyObject.playlist_all_tracks(playlist_id)

print("Criando diretório da playlist: "+ playlist_name)

path_to_download = "/home/lucas/"
playlist_path = os.path.join(path_to_download, playlist_name)
if not os.path.exists(playlist_path):
    os.makedirs(playlist_path)

# Playlist tracks information
tracks = resume_tracks_info(all_track_info)
tracks_count = len(tracks)
seq = 1
for t in tracks:
    q = str(t['artist'] + " - " + t['name'])
    print("Buscando melhor match com: "+q+" ...")
    videos_search = youtube_search(q, max_videos_result)
    video_id = min_time_diff(t['duration'], videos_search)[0]
    url_list = []
    url_list.append("https://www.youtube.com/watch?v=" + video_id)

    output_str = playlist_path+"/"+str(seq)+" - "+q
    ydl_opts = {
        'verbose': False,
        'quiet': True,
        'format': 'bestaudio/best',
        'outtmpl': output_str+'.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    print("Download ["+str(seq)+"/"+str(tracks_count)+"]: "+q+" ...")

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download(url_list)
    
    seq += 1

print("Pronto!")
