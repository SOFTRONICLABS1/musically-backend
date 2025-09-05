import logging
import re
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse, parse_qs
import requests
import subprocess
import tempfile
import os
import json

# Music analysis libraries (install as needed)
try:
    import librosa
    import numpy as np
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logging.warning("librosa not installed - music analysis features limited")
    # Define np for type hints even if numpy not available
    class np:
        ndarray = list

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    logging.warning("yt-dlp not installed - YouTube extraction limited")

from app.core.config import settings

logger = logging.getLogger(__name__)


class MusicExtractionService:
    """Service for extracting musical information from social media links"""
    
    # YouTube API endpoint
    YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
    
    # Musical note mappings
    NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    @staticmethod
    def extract_youtube_video_id(url: str) -> Optional[str]:
        """Extract YouTube video ID from various URL formats"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?]*)',
            r'youtube\.com\/watch\?.*v=([^&\n?]*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    @staticmethod
    def get_youtube_metadata(video_id: str) -> Optional[Dict]:
        """Get metadata from YouTube using API or yt-dlp"""
        
        # Try YouTube Data API first if API key is available
        if hasattr(settings, 'YOUTUBE_API_KEY') and settings.YOUTUBE_API_KEY:
            try:
                url = f"{MusicExtractionService.YOUTUBE_API_BASE}/videos"
                params = {
                    'part': 'snippet,contentDetails',
                    'id': video_id,
                    'key': settings.YOUTUBE_API_KEY
                }
                
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if data['items']:
                        item = data['items'][0]
                        return {
                            'title': item['snippet']['title'],
                            'description': item['snippet']['description'],
                            'duration': item['contentDetails']['duration'],
                            'channel': item['snippet']['channelTitle'],
                            'tags': item['snippet'].get('tags', [])
                        }
            except Exception as e:
                logger.error(f"YouTube API error: {e}")
        
        # Fallback to yt-dlp for metadata
        if YTDLP_AVAILABLE:
            try:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': True
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
                    return {
                        'title': info.get('title'),
                        'description': info.get('description'),
                        'duration': info.get('duration'),
                        'channel': info.get('uploader'),
                        'tags': info.get('tags', [])
                    }
            except Exception as e:
                logger.error(f"yt-dlp metadata extraction error: {e}")
        
        return None
    
    @staticmethod
    def download_audio_from_youtube(video_id: str, output_path: str) -> bool:
        """Download audio from YouTube video"""
        
        if not YTDLP_AVAILABLE:
            logger.error("yt-dlp not available for audio download")
            return False
        
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
                'outtmpl': output_path.replace('.wav', ''),
                'quiet': True,
                'no_warnings': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://youtube.com/watch?v={video_id}"])
            
            return os.path.exists(output_path)
            
        except Exception as e:
            logger.error(f"Audio download error: {e}")
            return False
    
    @staticmethod
    def analyze_audio_file(audio_path: str) -> Dict[str, Any]:
        """Analyze audio file for musical properties"""
        
        if not LIBROSA_AVAILABLE:
            logger.warning("librosa not available - returning basic analysis")
            return {
                'tempo': 120,  # Default tempo
                'key': 'C',
                'time_signature': '4/4',
                'notes_data': None
            }
        
        try:
            # Load audio file
            y, sr = librosa.load(audio_path, duration=60)  # Analyze first 60 seconds
            
            # Extract tempo
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            tempo = float(tempo)
            
            # Extract pitch/chroma features for key detection
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            chroma_mean = np.mean(chroma, axis=1)
            
            # Estimate key (simplified)
            key_index = np.argmax(chroma_mean)
            estimated_key = MusicExtractionService.NOTES[key_index]
            
            # Detect onset times for rhythm pattern
            onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
            onset_times = librosa.frames_to_time(onset_frames, sr=sr)
            
            # Extract harmonic and percussive components
            y_harmonic, y_percussive = librosa.effects.hpss(y)
            
            # Generate basic notes data structure
            notes_data = MusicExtractionService.generate_notes_data(
                tempo=tempo,
                key=estimated_key,
                onset_times=onset_times[:50],  # First 50 notes
                chroma=chroma
            )
            
            return {
                'tempo': int(tempo),
                'key': estimated_key,
                'time_signature': '4/4',  # Default, could be enhanced
                'energy': float(np.mean(librosa.feature.rms(y=y))),
                'notes_data': notes_data
            }
            
        except Exception as e:
            logger.error(f"Audio analysis error: {e}")
            return {
                'tempo': 120,
                'key': 'C',
                'time_signature': '4/4',
                'notes_data': None
            }
    
    @staticmethod
    def generate_notes_data(tempo: float, key: str, onset_times: np.ndarray, chroma: np.ndarray) -> Dict:
        """Generate notes_data structure from audio analysis"""
        
        notes = []
        
        # Generate notes based on onset times and chroma features
        for i, onset_time in enumerate(onset_times):
            if i < chroma.shape[1]:
                # Get dominant pitch at this time
                chroma_frame = chroma[:, i]
                note_index = np.argmax(chroma_frame)
                note_name = MusicExtractionService.NOTES[note_index]
                
                # Calculate duration (time to next onset or default)
                duration = 0.5  # Default half second
                if i < len(onset_times) - 1:
                    duration = min(onset_times[i + 1] - onset_time, 2.0)
                
                notes.append({
                    'note': note_name,
                    'octave': 4,  # Default octave
                    'duration': round(duration, 2),
                    'time': round(onset_time, 2),
                    'velocity': 0.7  # Default velocity
                })
        
        return {
            'format': 'extracted',
            'tempo': int(tempo),
            'key': key,
            'time_signature': '4/4',
            'measures': [
                {
                    'number': i + 1,
                    'notes': notes[i*4:(i+1)*4]  # 4 notes per measure (simplified)
                }
                for i in range(min(8, len(notes) // 4))  # Up to 8 measures
            ],
            'metadata': {
                'source': 'audio_extraction',
                'confidence': 0.7  # Confidence score
            }
        }
    
    @staticmethod
    def extract_music_from_social_link(url: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Main method to extract musical information from social media link
        Returns tuple of (metadata, notes_data)
        """
        
        # Currently focusing on YouTube
        video_id = MusicExtractionService.extract_youtube_video_id(url)
        if not video_id:
            logger.warning(f"Could not extract video ID from URL: {url}")
            return None, None
        
        # Get video metadata
        metadata = MusicExtractionService.get_youtube_metadata(video_id)
        if not metadata:
            logger.warning(f"Could not get metadata for video: {video_id}")
            return None, None
        
        # Check if it's likely music content based on metadata
        is_music = MusicExtractionService.is_likely_music_content(metadata)
        if not is_music:
            logger.info(f"Video doesn't appear to be music content: {metadata.get('title')}")
            # Still return metadata but no notes_data
            return metadata, None
        
        # Download and analyze audio (optional - can be async/queued)
        notes_data = None
        if YTDLP_AVAILABLE and LIBROSA_AVAILABLE:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                temp_path = tmp_file.name
                
            try:
                # Download audio
                if MusicExtractionService.download_audio_from_youtube(video_id, temp_path):
                    # Analyze audio
                    analysis = MusicExtractionService.analyze_audio_file(temp_path)
                    notes_data = analysis.get('notes_data')
                    
                    # Add analysis results to metadata
                    metadata['tempo'] = analysis.get('tempo')
                    metadata['key'] = analysis.get('key')
                    metadata['energy'] = analysis.get('energy')
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        return metadata, notes_data
    
    @staticmethod
    def is_likely_music_content(metadata: Dict) -> bool:
        """Determine if content is likely music based on metadata"""
        
        music_keywords = [
            'music', 'song', 'album', 'artist', 'band', 'concert', 'live',
            'official video', 'lyrics', 'cover', 'remix', 'instrumental',
            'piano', 'guitar', 'drums', 'bass', 'violin', 'orchestra'
        ]
        
        # Check title and description
        title = (metadata.get('title') or '').lower()
        description = (metadata.get('description') or '').lower()
        tags = [tag.lower() for tag in metadata.get('tags', [])]
        
        # Check for music keywords
        for keyword in music_keywords:
            if keyword in title or keyword in description or keyword in tags:
                return True
        
        # Check channel name for music-related terms
        channel = (metadata.get('channel') or '').lower()
        if any(term in channel for term in ['music', 'records', 'vevo', 'official']):
            return True
        
        return False
    
    @staticmethod
    def generate_default_notes_data(metadata: Dict) -> Dict:
        """Generate default notes_data when audio analysis isn't available"""
        
        return {
            'format': 'default',
            'tempo': 120,
            'key': 'C',
            'time_signature': '4/4',
            'measures': [
                {
                    'number': 1,
                    'notes': [
                        {'note': 'C', 'octave': 4, 'duration': 1.0, 'time': 0.0, 'velocity': 0.7},
                        {'note': 'E', 'octave': 4, 'duration': 1.0, 'time': 1.0, 'velocity': 0.7},
                        {'note': 'G', 'octave': 4, 'duration': 1.0, 'time': 2.0, 'velocity': 0.7},
                        {'note': 'C', 'octave': 5, 'duration': 1.0, 'time': 3.0, 'velocity': 0.7}
                    ]
                }
            ],
            'metadata': {
                'source': 'default_template',
                'video_title': metadata.get('title'),
                'confidence': 0.3
            }
        }


# Service instance
music_extraction_service = MusicExtractionService()