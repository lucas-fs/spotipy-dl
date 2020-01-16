from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

import spotipy
from spotipy import util, client
from spotipy.oauth2 import SpotifyClientCredentials

import youtube_dl

import json
from json.decoder import JSONDecodeError

import unicodedata
import argparse
import re
import os


# =========== Credentials ===========


# YouTube API
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

# Spotify API
client_id = ""
client_secret = ""
redirect_url = "https://google.com"

# =========== Util ===========


def read_yt_apikeys():
    yt_keys = []
    with open("yt_apikeys.txt", 'r') as f:
        yt_keys = f.read().splitlines()
    return yt_keys


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
        track['duration'] = t['track']['duration_ms']
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


def youtube_search(query, max_results, api_key):
    yout = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                    developerKey=api_key)

    search_response = yout.search().list(
        q=query,
        part="id",
        type="video",
        fields="items/id/videoId",
        maxResults=max_results
    ).execute()

    search_videos = []

    # Merge video ids
    for search_result in search_response.get('items', []):
        search_videos.append(search_result['id']['videoId'])
    video_ids = ','.join(search_videos)

    # Call the videos.list method to retrieve location details for each video.
    video_response = yout.videos().list(
        part="contentDetails",
        id=video_ids,
        fields="items(id, contentDetails(duration, definition))"
    ).execute()

    videos = []

    for video_result in video_response.get('items', []):
        v = {}

        v['id'] = video_result['id']
        v['duration'] = to_milissec(video_result['contentDetails']['duration'])
        v['definition'] = video_result['contentDetails']['definition']

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

def get_token(username, client_id, client_secret, redirect_url):

    scope = 'playlist-read-private'
    # Erase cache and prompt for user permission
    try:
        token = util.prompt_for_user_token(
            username, scope, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_url)
    except (AttributeError, JSONDecodeError):
        os.remove(f".cache-{username}")
        token = util.prompt_for_user_token(
            username, scope, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_url)
    return token

# =========== Execution ===========

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--playlist', help='Playlist URI', default=None)
    parser.add_argument('--uid', help='Spotify user ID', default=None)
    parser.add_argument('--max-matches', help='Max matches', default=8)
    parser.add_argument('--output', help='Path to output files', default='')
    args = parser.parse_args()

    if (not args.playlist or not args.uid):
        print("Playlist URI e/ou Spotify user não informados!")
        exit()  

    max_matches = args.max_matches
    username = args.uid

    token = get_token(username, client_id, client_secret, redirect_url)
    client_credentials_manager = SpotifyClientCredentials(
        client_id=client_id, client_secret=client_secret)
    spotifyObject = client.Spotify(
        auth=token, client_credentials_manager=client_credentials_manager)

    print("Capturando informações da playlist...")

    playlist_id = get_playlist_id(args.playlist)
    playlist_info = spotifyObject.playlist_information(playlist_id, "name")
    playlist_name = normalize_unicodes(playlist_info['name'])

    all_track_info = spotifyObject.playlist_all_tracks(playlist_id)

    print("Criando diretório da playlist: "+ playlist_name)

    output_path = args.output
    playlist_path = os.path.join(output_path, playlist_name)
    if not os.path.exists(playlist_path):
        os.makedirs(playlist_path)
    
    print("Caminho para os arquivos: "+playlist_path)

    # Load api keys
    used_key = 0
    yt_keys = read_yt_apikeys()
    keys_count = len(yt_keys)

    # Playlist tracks information
    tracks = resume_tracks_info(all_track_info)
    tracks_count = len(tracks)

    # Download files
    i = 0
    while (i < tracks_count):
        q = str(tracks[i]['artist'] + " - " + tracks[i]['name'])
        print("Buscando melhor match com: "+q+" ...")

        try:
            videos_search = youtube_search(q, max_matches, yt_keys[used_key])
        except HttpError as e:
            error = json.loads(e.content.decode("utf-8"))
            if (error["error"]["errors"][0]["reason"] == "quotaExceeded"):
                used_key += 1
                if (used_key >= keys_count):
                    print("Cota de downloads excedida!\n Cancelando downloads...")
                    break
                else:
                    continue
            else:
                print("Erro [%d] encontrado durante o download!" % e.resp.status)
                print_json(error)
                break

        video_id = min_time_diff(tracks[i]['duration'], videos_search)[0]
        url_list = []
        url_list.append("https://www.youtube.com/watch?v=" + video_id)

        output_str = playlist_path+"/"+str(i)+" - "+q
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

        print("Download ["+str(i+1)+"/"+str(tracks_count)+"]: "+q+" ...")

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download(url_list)
        
        i += 1

    print("Processo concluido!")
