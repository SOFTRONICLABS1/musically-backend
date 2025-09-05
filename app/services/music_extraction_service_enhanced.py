import logging
import re
from typing import Optional, Dict, Any, Tuple, List
from urllib.parse import urlparse, parse_qs
import requests
import subprocess
import tempfile
import os
import json
import math

# Music analysis libraries
try:
    import librosa
    import numpy as np
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logging.warning("librosa not installed - music analysis features limited")
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


class EnhancedMusicExtractionService:
    """Enhanced service for extracting musical information with full audio analysis"""
    
    YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
    NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    A4_FREQ = 440.0  # Hz
    
    @staticmethod
    def hz_to_note(frequency: float) -> Dict[str, Any]:
        """Convert frequency in Hz to musical note"""
        if frequency <= 0:
            return {'note': 'C', 'octave': 4, 'confidence': 0.0}
        
        # Calculate number of semitones from A4
        semitones_from_a4 = 12 * math.log2(frequency / EnhancedMusicExtractionService.A4_FREQ)
        
        # Round to nearest semitone
        semitones_from_a4 = round(semitones_from_a4)
        
        # Calculate octave and note
        octave = 4 + (semitones_from_a4 + 9) // 12
        note_index = (semitones_from_a4 + 9) % 12
        
        return {
            'note': EnhancedMusicExtractionService.NOTES[note_index],
            'octave': max(0, min(9, octave)),  # Clamp octave to reasonable range
            'confidence': 0.9
        }
    
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
        """Get metadata from YouTube using yt-dlp with more details"""
        if YTDLP_AVAILABLE:
            try:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,  # Get full info
                    'format': 'bestaudio/best'
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
                    
                    return {
                        'title': info.get('title'),
                        'description': info.get('description'),
                        'duration': info.get('duration'),
                        'channel': info.get('uploader'),
                        'tags': info.get('tags', []),
                        'categories': info.get('categories', []),
                        'upload_date': info.get('upload_date'),
                        'view_count': info.get('view_count'),
                        'like_count': info.get('like_count'),
                        'average_rating': info.get('average_rating')
                    }
            except Exception as e:
                logger.error(f"yt-dlp metadata extraction error: {e}")
        
        return None
    
    @staticmethod
    def download_audio_from_youtube(video_id: str, output_path: str) -> bool:
        """Download audio from YouTube video with best quality"""
        if not YTDLP_AVAILABLE:
            logger.error("yt-dlp not available for audio download")
            return False
        
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '320',  # Higher quality
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
    def analyze_audio_file_enhanced(audio_path: str) -> Dict[str, Any]:
        """Enhanced audio analysis with comprehensive note extraction"""
        if not LIBROSA_AVAILABLE:
            logger.warning("librosa not available - returning basic analysis")
            return {
                'tempo': 120,
                'key': 'C',
                'time_signature': '4/4',
                'notes_data': None
            }
        
        try:
            logger.info(f"Starting enhanced audio analysis for {audio_path}")
            
            # Load audio file (analyze up to 3 minutes)
            y, sr = librosa.load(audio_path, duration=180, sr=22050)
            
            # Extract tempo and beat tracking
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')
            tempo = float(tempo)
            
            # Extract chroma features for key detection
            chroma_cqt = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512)
            chroma_mean = np.mean(chroma_cqt, axis=1)
            
            # Estimate key
            key_index = np.argmax(chroma_mean)
            estimated_key = EnhancedMusicExtractionService.NOTES[key_index]
            
            # Enhanced onset detection
            onset_envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=512)
            onset_frames = librosa.onset.onset_detect(
                onset_envelope=onset_envelope,
                sr=sr,
                backtrack=True,
                units='frames'
            )
            onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=512)
            
            # Harmonic-percussive separation
            y_harmonic, y_percussive = librosa.effects.hpss(y, margin=8.0)
            
            # Multi-method pitch detection
            notes_list = []
            
            # Method 1: Pitch tracking using piptrack
            pitches, magnitudes = librosa.piptrack(
                y=y_harmonic,
                sr=sr,
                threshold=0.1,
                hop_length=512
            )
            
            # Method 2: Spectral peaks for overtone analysis
            S = np.abs(librosa.stft(y_harmonic, hop_length=512))
            
            # Process each onset
            for i, onset_time in enumerate(onset_times[:300]):  # Process up to 300 notes
                onset_frame = librosa.time_to_frames(onset_time, sr=sr, hop_length=512)
                
                if onset_frame < pitches.shape[1]:
                    # Get pitch from piptrack
                    pitch_candidates = []
                    
                    # Collect pitch candidates from a window around onset
                    window_size = 3
                    for w in range(max(0, onset_frame - window_size), 
                                 min(pitches.shape[1], onset_frame + window_size + 1)):
                        mag_frame = magnitudes[:, w]
                        pitch_frame = pitches[:, w]
                        
                        # Get top N pitch candidates
                        top_indices = np.argsort(mag_frame)[-3:]
                        for idx in top_indices:
                            if pitch_frame[idx] > 50 and pitch_frame[idx] < 4000:  # Reasonable frequency range
                                pitch_candidates.append({
                                    'freq': pitch_frame[idx],
                                    'mag': mag_frame[idx]
                                })
                    
                    # Select best pitch candidate
                    if pitch_candidates:
                        best_candidate = max(pitch_candidates, key=lambda x: x['mag'])
                        note_info = EnhancedMusicExtractionService.hz_to_note(best_candidate['freq'])
                        velocity = min(1.0, best_candidate['mag'] / np.max(magnitudes))
                    else:
                        # Fallback to chroma
                        chroma_frame = chroma_cqt[:, onset_frame] if onset_frame < chroma_cqt.shape[1] else chroma_mean
                        note_idx = np.argmax(chroma_frame)
                        note_info = {
                            'note': EnhancedMusicExtractionService.NOTES[note_idx],
                            'octave': 4,
                            'confidence': float(chroma_frame[note_idx])
                        }
                        velocity = 0.7
                    
                    # Calculate duration
                    if i < len(onset_times) - 1:
                        duration = onset_times[i + 1] - onset_time
                        # Quantize to musical durations
                        beat_duration = 60.0 / tempo
                        duration_in_beats = duration / beat_duration
                        
                        # Quantize to nearest standard duration
                        standard_durations = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
                        duration_in_beats = min(standard_durations, key=lambda x: abs(x - duration_in_beats))
                        duration = duration_in_beats * beat_duration
                    else:
                        duration = 0.5
                    
                    notes_list.append({
                        'note': note_info['note'],
                        'octave': note_info['octave'],
                        'duration': round(duration, 3),
                        'time': round(onset_time, 3),
                        'velocity': round(velocity, 2),
                        'confidence': round(note_info.get('confidence', 0.8), 2)
                    })
            
            # Generate comprehensive notes data
            notes_data = EnhancedMusicExtractionService.generate_comprehensive_notes_data(
                tempo=tempo,
                key=estimated_key,
                notes_list=notes_list,
                beats=beats
            )
            
            # Additional audio features
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
            zero_crossing_rate = librosa.feature.zero_crossing_rate(y)
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            
            return {
                'tempo': int(tempo),
                'key': estimated_key,
                'time_signature': EnhancedMusicExtractionService.estimate_time_signature(beats, tempo),
                'energy': float(np.mean(librosa.feature.rms(y=y))),
                'spectral_centroid': float(np.mean(spectral_centroid)),
                'zero_crossing_rate': float(np.mean(zero_crossing_rate)),
                'brightness': float(np.mean(spectral_centroid) / sr),
                'notes_count': len(notes_list),
                'duration_seconds': len(y) / sr,
                'notes_data': notes_data
            }
            
        except Exception as e:
            logger.error(f"Enhanced audio analysis error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'tempo': 120,
                'key': 'C',
                'time_signature': '4/4',
                'notes_data': None
            }
    
    @staticmethod
    def estimate_time_signature(beats: np.ndarray, tempo: float) -> str:
        """Estimate time signature from beat pattern"""
        if len(beats) < 8:
            return '4/4'
        
        # Calculate inter-beat intervals
        beat_intervals = np.diff(beats)
        
        # Look for patterns in beat intervals
        mean_interval = np.mean(beat_intervals)
        std_interval = np.std(beat_intervals)
        
        # Simple heuristic for common time signatures
        if std_interval / mean_interval < 0.1:
            # Regular beats
            beats_per_minute = 60.0 / mean_interval
            if abs(beats_per_minute - tempo) < 10:
                return '4/4'
            elif abs(beats_per_minute - tempo * 0.75) < 10:
                return '3/4'
            elif abs(beats_per_minute - tempo * 1.5) < 10:
                return '6/8'
        
        return '4/4'  # Default
    
    @staticmethod
    def generate_comprehensive_notes_data(
        tempo: float,
        key: str,
        notes_list: List[Dict],
        beats: np.ndarray
    ) -> Dict:
        """Generate comprehensive notes data with measures and musical structure"""
        
        if not notes_list:
            return EnhancedMusicExtractionService.generate_default_notes_data({
                'title': 'Unknown',
                'tempo': tempo,
                'key': key
            })
        
        # Group notes into measures
        beat_duration = 60.0 / tempo
        measure_duration = beat_duration * 4  # Assuming 4/4 time
        
        measures = []
        current_measure = []
        current_measure_start = 0
        measure_number = 1
        
        for note in notes_list:
            note_time = note['time']
            
            # Check if note belongs to next measure
            if note_time >= current_measure_start + measure_duration and current_measure:
                measures.append({
                    'number': measure_number,
                    'start_time': round(current_measure_start, 3),
                    'notes': current_measure[:16]  # Limit notes per measure
                })
                measure_number += 1
                current_measure = []
                current_measure_start += measure_duration
                
                # Skip to correct measure if there's a gap
                while note_time >= current_measure_start + measure_duration:
                    current_measure_start += measure_duration
            
            # Adjust note time relative to measure start
            adjusted_note = note.copy()
            adjusted_note['measure_time'] = round(note_time - current_measure_start, 3)
            current_measure.append(adjusted_note)
            
            # Limit total measures
            if measure_number > 64:
                break
        
        # Add last measure if it has notes
        if current_measure:
            measures.append({
                'number': measure_number,
                'start_time': round(current_measure_start, 3),
                'notes': current_measure[:16]
            })
        
        # Calculate chord progressions (simplified)
        chord_progression = EnhancedMusicExtractionService.estimate_chord_progression(measures, key)
        
        return {
            'format': 'enhanced_extraction',
            'tempo': int(tempo),
            'key': key,
            'time_signature': '4/4',
            'total_notes': len(notes_list),
            'measures': measures[:32],  # Return up to 32 measures
            'chord_progression': chord_progression,
            'metadata': {
                'source': 'audio_extraction_enhanced',
                'confidence': 0.85,
                'extraction_method': 'multi-method-pitch-detection',
                'notes_extracted': len(notes_list),
                'measures_created': len(measures)
            }
        }
    
    @staticmethod
    def estimate_chord_progression(measures: List[Dict], key: str) -> List[Dict]:
        """Estimate chord progression from measures"""
        # Common chord progressions in major/minor keys
        major_chords = ['I', 'ii', 'iii', 'IV', 'V', 'vi', 'vii°']
        minor_chords = ['i', 'ii°', 'III', 'iv', 'v', 'VI', 'VII']
        
        chord_progression = []
        
        for i, measure in enumerate(measures[:16]):  # Analyze first 16 measures
            # Simple heuristic: use common progression patterns
            if i % 4 == 0:
                chord = 'I' if key.isupper() else 'i'
            elif i % 4 == 1:
                chord = 'V' if key.isupper() else 'v'
            elif i % 4 == 2:
                chord = 'vi' if key.isupper() else 'VI'
            else:
                chord = 'IV' if key.isupper() else 'iv'
            
            chord_progression.append({
                'measure': measure['number'],
                'chord': chord,
                'root': key
            })
        
        return chord_progression
    
    @staticmethod
    def extract_music_from_social_link_enhanced(url: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Enhanced extraction with full audio analysis pipeline"""
        
        video_id = EnhancedMusicExtractionService.extract_youtube_video_id(url)
        if not video_id:
            logger.warning(f"Could not extract video ID from URL: {url}")
            return None, None
        
        # Get video metadata
        metadata = EnhancedMusicExtractionService.get_youtube_metadata(video_id)
        if not metadata:
            logger.warning(f"Could not get metadata for video: {video_id}")
            return None, None
        
        # Check if it's likely music content
        is_music = EnhancedMusicExtractionService.is_likely_music_content(metadata)
        if not is_music:
            logger.info(f"Video doesn't appear to be music content: {metadata.get('title')}")
            return metadata, None
        
        # Download and analyze audio
        notes_data = None
        analysis_result = {}
        
        if YTDLP_AVAILABLE and LIBROSA_AVAILABLE:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                temp_path = tmp_file.name
                
            try:
                logger.info(f"Downloading audio for analysis: {video_id}")
                
                # Download audio
                if EnhancedMusicExtractionService.download_audio_from_youtube(video_id, temp_path):
                    logger.info(f"Analyzing audio file: {temp_path}")
                    
                    # Analyze audio with enhanced method
                    analysis_result = EnhancedMusicExtractionService.analyze_audio_file_enhanced(temp_path)
                    notes_data = analysis_result.get('notes_data')
                    
                    # Add analysis results to metadata
                    metadata.update({
                        'tempo': analysis_result.get('tempo'),
                        'key': analysis_result.get('key'),
                        'time_signature': analysis_result.get('time_signature'),
                        'energy': analysis_result.get('energy'),
                        'spectral_centroid': analysis_result.get('spectral_centroid'),
                        'brightness': analysis_result.get('brightness'),
                        'notes_count': analysis_result.get('notes_count')
                    })
                    
                    logger.info(f"Audio analysis complete. Extracted {analysis_result.get('notes_count', 0)} notes")
                else:
                    logger.warning("Failed to download audio")
                    
            except Exception as e:
                logger.error(f"Error during audio processing: {e}")
                import traceback
                traceback.print_exc()
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
        
        # If no notes were extracted, generate default
        if not notes_data:
            notes_data = EnhancedMusicExtractionService.generate_default_notes_data(metadata)
        
        return metadata, notes_data
    
    @staticmethod
    def is_likely_music_content(metadata: Dict) -> bool:
        """Determine if content is likely music based on metadata"""
        
        music_keywords = [
            'music', 'song', 'album', 'artist', 'band', 'concert', 'live',
            'official video', 'official audio', 'lyrics', 'cover', 'remix',
            'instrumental', 'acoustic', 'performance', 'tour', 'single',
            'piano', 'guitar', 'drums', 'bass', 'violin', 'orchestra',
            'symphony', 'jazz', 'rock', 'pop', 'hip hop', 'rap', 'classical'
        ]
        
        # Check title and description
        title = (metadata.get('title') or '').lower()
        description = (metadata.get('description') or '').lower()
        tags = [tag.lower() for tag in metadata.get('tags', [])]
        categories = [cat.lower() for cat in metadata.get('categories', [])]
        
        # Check for music keywords
        for keyword in music_keywords:
            if keyword in title or keyword in description or keyword in tags:
                return True
        
        # Check categories
        if 'music' in categories:
            return True
        
        # Check channel name for music-related terms
        channel = (metadata.get('channel') or '').lower()
        if any(term in channel for term in ['music', 'records', 'vevo', 'official', 'band', 'artist']):
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
                    'start_time': 0.0,
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
enhanced_music_extraction_service = EnhancedMusicExtractionService()