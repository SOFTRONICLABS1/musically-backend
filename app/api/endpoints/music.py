from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging

# Import based on available libraries
import os

if os.environ.get('AWS_LAMBDA_FUNCTION_NAME', '').endswith('music-extractor'):
    # Use enhanced service in music-extractor Lambda
    from app.services.music_extraction_service_enhanced import enhanced_music_extraction_service as music_extraction_service
else:
    # Use basic service in other Lambdas
    from app.services.music_extraction_service import music_extraction_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Music"])


@router.post("/extract")
async def extract_music_from_url(
    url: str = Query(..., description="Social media URL to extract music from")
):
    """
    Extract music data from social media URL
    This endpoint runs on the firebase-auth Lambda (no VPC, has internet access)
    """
    try:
        logger.info(f"Extracting music from URL: {url}")
        
        # Extract music data
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME', '').endswith('music-extractor'):
            # Use enhanced extraction in music Lambda
            metadata, notes_data = music_extraction_service.extract_music_from_social_link_enhanced(url)
        else:
            metadata, notes_data = music_extraction_service.extract_music_from_social_link(url)
        
        if not metadata:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Could not extract metadata from URL"
                }
            )
        
        # Check if it's music content
        is_music = music_extraction_service.is_likely_music_content(metadata)
        
        # Generate default notes if no extraction but is music
        if not notes_data and is_music:
            notes_data = music_extraction_service.generate_default_notes_data(metadata)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "is_music_content": is_music,
                "metadata": metadata,
                "notes_data": notes_data,
                "message": "Music data extracted successfully" if notes_data else "No music data found"
            }
        )
        
    except Exception as e:
        logger.error(f"Music extraction error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error extracting music: {str(e)}"
            }
        )


@router.post("/validate-youtube")
async def validate_youtube_url(
    url: str = Query(..., description="YouTube URL to validate")
):
    """
    Validate YouTube URL and get basic metadata
    """
    try:
        # Extract video ID
        video_id = music_extraction_service.extract_youtube_video_id(url)
        
        if not video_id:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Invalid YouTube URL"
                }
            )
        
        # Get metadata
        metadata = music_extraction_service.get_youtube_metadata(video_id)
        
        if not metadata:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "Could not retrieve video metadata"
                }
            )
        
        # Check if it's music
        is_music = music_extraction_service.is_likely_music_content(metadata)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "video_id": video_id,
                "is_music": is_music,
                "metadata": metadata
            }
        )
        
    except Exception as e:
        logger.error(f"YouTube validation error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error validating YouTube URL: {str(e)}"
            }
        )


@router.post("/analyze")
async def analyze_audio_url(
    url: str = Query(..., description="YouTube URL to analyze for detailed music extraction")
):
    """
    Analyze audio from YouTube URL with enhanced music extraction
    This endpoint uses advanced audio analysis with librosa for detailed note extraction
    """
    try:
        logger.info(f"Analyzing audio from URL: {url}")
        
        # Check if we're in the music-extractor Lambda
        if not os.environ.get('AWS_LAMBDA_FUNCTION_NAME', '').endswith('music-extractor'):
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error": "Enhanced audio analysis only available on music-extractor Lambda"
                }
            )
        
        # Extract video ID
        video_id = music_extraction_service.extract_youtube_video_id(url)
        
        if not video_id:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Invalid YouTube URL"
                }
            )
        
        # Use enhanced extraction
        metadata, notes_data = music_extraction_service.extract_music_from_social_link_enhanced(url)
        
        if not metadata:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Could not extract metadata from URL"
                }
            )
        
        # Get detailed analysis info
        analysis_info = {
            "video_id": video_id,
            "title": metadata.get('title'),
            "duration": metadata.get('duration'),
            "channel": metadata.get('channel'),
            "is_music": music_extraction_service.is_likely_music_content(metadata),
            "tempo": metadata.get('tempo'),
            "key": metadata.get('key'),
            "time_signature": metadata.get('time_signature'),
            "energy": metadata.get('energy'),
            "spectral_centroid": metadata.get('spectral_centroid'),
            "brightness": metadata.get('brightness'),
            "notes_count": metadata.get('notes_count', 0)
        }
        
        # Count measures if notes_data exists
        measures_count = 0
        total_notes = 0
        if notes_data and 'measures' in notes_data:
            measures_count = len(notes_data.get('measures', []))
            total_notes = notes_data.get('total_notes', 0)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "analysis": analysis_info,
                "notes_summary": {
                    "total_notes": total_notes,
                    "measures_count": measures_count,
                    "extraction_format": notes_data.get('format') if notes_data else None,
                    "confidence": notes_data.get('metadata', {}).get('confidence', 0) if notes_data else 0
                },
                "notes_data": notes_data,
                "message": f"Successfully analyzed audio and extracted {total_notes} notes"
            }
        )
        
    except Exception as e:
        logger.error(f"Audio analysis error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error analyzing audio: {str(e)}"
            }
        )