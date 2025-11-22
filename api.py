"""FastAPI web application for ComicCrafter."""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from pathlib import Path
import uuid
import json
from datetime import datetime

from agents.story_agent import Scene
from utils import get_config, get_logger
from core import ComicCrafter

logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ComicCrafter API",
    description="Zero-cost multi-agent AI system for automatic comic generation",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Job storage (in production, use a database)
jobs = {}

# Request/Response Models
class ComicRequest(BaseModel):
    """Request model for comic generation."""
    story_text: str = Field(..., description="Story text to convert to comic")
    style: str = Field("comic book style", description="Visual style for the comic")
    max_scenes: Optional[int] = Field(None, description="Maximum number of scenes")
    add_dialogue: bool = Field(True, description="Whether to add dialogue overlays")
    llm_provider: str = Field("groq", description="LLM provider (groq or gemini)")
    output_name: Optional[str] = Field(None, description="Base name for output files")


class SceneRequest(BaseModel):
    """Request model for scene-based generation."""
    scenes: List[dict] = Field(..., description="List of scene dictionaries")
    style: str = Field("comic book style", description="Visual style")
    add_dialogue: bool = Field(True, description="Add dialogue overlays")
    llm_provider: str = Field("groq", description="LLM provider")


class JobStatus(BaseModel):
    """Job status response."""
    job_id: str
    status: str  # pending, processing, completed, failed
    message: str
    created_at: str
    completed_at: Optional[str] = None
    output_files: Optional[List[str]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    api_keys_configured: dict


# Helper functions
def create_job(job_id: str, message: str = "Job created") -> None:
    """Create a new job entry."""
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "message": message,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "output_files": None,
        "error": None
    }


def update_job(job_id: str, **kwargs) -> None:
    """Update job status."""
    if job_id in jobs:
        jobs[job_id].update(kwargs)


def generate_comic_task(
    job_id: str,
    story_text: str,
    style: str,
    max_scenes: Optional[int],
    add_dialogue: bool,
    llm_provider: str,
    output_name: Optional[str]
):
    """Background task for comic generation."""
    try:
        update_job(job_id, status="processing", message="Initializing ComicCrafter...")
        
        # Initialize ComicCrafter
        crafter = ComicCrafter(llm_provider=llm_provider)
        
        # Generate output name
        if not output_name:
            output_name = f"comic_{job_id[:8]}"
        
        update_job(job_id, message="Generating comic...")
        
        # Generate comic
        output_paths = crafter.generate_comic(
            story_text=story_text,
            style=style,
            max_scenes=max_scenes,
            add_dialogue=add_dialogue,
            output_name=output_name
        )
        
        # Convert paths to strings
        output_files = [str(path) for path in output_paths]
        
        update_job(
            job_id,
            status="completed",
            message="Comic generation completed successfully",
            completed_at=datetime.now().isoformat(),
            output_files=output_files
        )
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        error_msg = str(e)
        update_job(
            job_id,
            status="failed",
            message="Comic generation failed",
            completed_at=datetime.now().isoformat(),
            error=error_msg
        )
        logger.error(f"Job {job_id} failed: {error_msg}")


# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web interface."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ComicCrafter - AI Comic Generator</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            h1 {
                color: #667eea;
                margin-bottom: 10px;
                font-size: 2.5em;
            }
            .subtitle {
                color: #666;
                margin-bottom: 30px;
                font-size: 1.1em;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 8px;
                color: #333;
                font-weight: 600;
            }
            textarea, input, select {
                width: 100%;
                padding: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 1em;
                transition: border-color 0.3s;
            }
            textarea {
                min-height: 150px;
                resize: vertical;
                font-family: inherit;
            }
            textarea:focus, input:focus, select:focus {
                outline: none;
                border-color: #667eea;
            }
            .checkbox-group {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .checkbox-group input[type="checkbox"] {
                width: auto;
            }
            button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px 40px;
                border: none;
                border-radius: 8px;
                font-size: 1.1em;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
            }
            button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            .status {
                margin-top: 30px;
                padding: 20px;
                border-radius: 8px;
                display: none;
            }
            .status.show { display: block; }
            .status.pending { background: #fff3cd; border-left: 4px solid #ffc107; }
            .status.processing { background: #cfe2ff; border-left: 4px solid #0d6efd; }
            .status.completed { background: #d1e7dd; border-left: 4px solid #28a745; }
            .status.failed { background: #f8d7da; border-left: 4px solid #dc3545; }
            .output-images {
                margin-top: 20px;
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 15px;
            }
            .output-images img {
                width: 100%;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                cursor: pointer;
                transition: transform 0.2s;
            }
            .output-images img:hover {
                transform: scale(1.05);
            }
            .footer {
                margin-top: 30px;
                text-align: center;
                color: #666;
                font-size: 0.9em;
            }
            .loading {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid rgba(102, 126, 234, 0.3);
                border-radius: 50%;
                border-top-color: #667eea;
                animation: spin 1s ease-in-out infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎨 ComicCrafter</h1>
            <p class="subtitle">Transform your stories into comics with AI</p>
            
            <form id="comicForm">
                <div class="form-group">
                    <label for="story">📖 Your Story</label>
                    <textarea id="story" name="story_text" required 
                        placeholder="Enter your story here... (e.g., A brave hero embarks on an epic quest...)"></textarea>
                </div>
                
                <div class="form-group">
                    <label for="style">🎨 Visual Style</label>
                    <input type="text" id="style" name="style" value="comic book style, graphic novel art"
                        placeholder="e.g., manga style, superhero comic">
                </div>
                
                <div class="form-group">
                    <label for="maxScenes">📐 Max Scenes (panels)</label>
                    <input type="number" id="maxScenes" name="max_scenes" min="1" max="12" value="6">
                </div>
                
                <div class="form-group">
                    <label for="llmProvider">🤖 AI Provider</label>
                    <select id="llmProvider" name="llm_provider">
                        <option value="groq">Groq (Llama 3.3)</option>
                        <option value="gemini">Google Gemini</option>
                    </select>
                </div>
                
                <div class="form-group checkbox-group">
                    <input type="checkbox" id="addDialogue" name="add_dialogue" checked>
                    <label for="addDialogue" style="margin-bottom: 0;">💬 Add Dialogue Bubbles</label>
                </div>
                
                <button type="submit" id="generateBtn">Generate Comic</button>
            </form>
            
            <div id="status" class="status">
                <div id="statusMessage"></div>
                <div class="output-images" id="outputImages"></div>
            </div>
            
            <div class="footer">
                <p>Powered by Groq, Google Gemini, and HuggingFace</p>
                <p>🆓 Zero-cost AI comic generation</p>
            </div>
        </div>
        
        <script>
            let currentJobId = null;
            let checkInterval = null;
            
            document.getElementById('comicForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = {
                    story_text: document.getElementById('story').value,
                    style: document.getElementById('style').value,
                    max_scenes: parseInt(document.getElementById('maxScenes').value),
                    llm_provider: document.getElementById('llmProvider').value,
                    add_dialogue: document.getElementById('addDialogue').checked
                };
                
                try {
                    document.getElementById('generateBtn').disabled = true;
                    document.getElementById('generateBtn').innerHTML = '<span class="loading"></span> Generating...';
                    
                    const response = await fetch('/api/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(formData)
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        currentJobId = data.job_id;
                        showStatus('pending', '⏳ Job created. Starting generation...');
                        startStatusCheck();
                    } else {
                        showStatus('failed', '❌ Error: ' + (data.detail || 'Unknown error'));
                        document.getElementById('generateBtn').disabled = false;
                        document.getElementById('generateBtn').textContent = 'Generate Comic';
                    }
                } catch (error) {
                    showStatus('failed', '❌ Error: ' + error.message);
                    document.getElementById('generateBtn').disabled = false;
                    document.getElementById('generateBtn').textContent = 'Generate Comic';
                }
            });
            
            function startStatusCheck() {
                checkInterval = setInterval(checkJobStatus, 2000);
            }
            
            async function checkJobStatus() {
                if (!currentJobId) return;
                
                try {
                    const response = await fetch(`/api/status/${currentJobId}`);
                    const data = await response.json();
                    
                    if (data.status === 'processing') {
                        showStatus('processing', '🎨 ' + data.message);
                    } else if (data.status === 'completed') {
                        clearInterval(checkInterval);
                        showStatus('completed', '✅ ' + data.message);
                        displayImages(data.output_files);
                        document.getElementById('generateBtn').disabled = false;
                        document.getElementById('generateBtn').textContent = 'Generate Comic';
                    } else if (data.status === 'failed') {
                        clearInterval(checkInterval);
                        showStatus('failed', '❌ ' + (data.error || data.message));
                        document.getElementById('generateBtn').disabled = false;
                        document.getElementById('generateBtn').textContent = 'Generate Comic';
                    }
                } catch (error) {
                    console.error('Status check error:', error);
                }
            }
            
            function showStatus(type, message) {
                const statusDiv = document.getElementById('status');
                const messageDiv = document.getElementById('statusMessage');
                
                statusDiv.className = 'status show ' + type;
                messageDiv.textContent = message;
            }
            
            function displayImages(files) {
                const imagesDiv = document.getElementById('outputImages');
                imagesDiv.innerHTML = '';
                
                files.forEach(file => {
                    const fileName = file.split('\\\\').pop().split('/').pop();
                    const img = document.createElement('img');
                    img.src = `/api/output/${fileName}`;
                    img.alt = fileName;
                    img.onclick = () => window.open(img.src, '_blank');
                    imagesDiv.appendChild(img);
                });
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    config = get_config()
    
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        api_keys_configured={
            "groq": bool(config.groq_api_key),
            "google": bool(config.google_api_key),
            "huggingface": bool(config.huggingface_token)
        }
    )


@app.post("/api/generate")
async def generate_comic(
    request: ComicRequest,
    background_tasks: BackgroundTasks
):
    """Generate a comic from story text."""
    # Validate API keys
    config = get_config()
    
    if request.llm_provider == "groq" and not config.groq_api_key:
        raise HTTPException(status_code=400, detail="Groq API key not configured")
    elif request.llm_provider == "gemini" and not config.google_api_key:
        raise HTTPException(status_code=400, detail="Google API key not configured")
    
    if not config.huggingface_token:
        raise HTTPException(status_code=400, detail="HuggingFace token not configured")
    
    # Create job
    job_id = str(uuid.uuid4())
    create_job(job_id, "Comic generation job created")
    
    # Add background task
    background_tasks.add_task(
        generate_comic_task,
        job_id=job_id,
        story_text=request.story_text,
        style=request.style,
        max_scenes=request.max_scenes,
        add_dialogue=request.add_dialogue,
        llm_provider=request.llm_provider,
        output_name=request.output_name
    )
    
    return {"job_id": job_id, "message": "Comic generation started"}


@app.get("/api/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status of a comic generation job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatus(**jobs[job_id])


@app.get("/api/jobs")
async def list_jobs():
    """List all jobs."""
    return {"jobs": list(jobs.values())}


@app.get("/api/output/{filename}")
async def get_output_file(filename: str):
    """Retrieve a generated comic page."""
    config = get_config()
    file_path = config.output_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its outputs."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    # Delete output files
    if job["output_files"]:
        for file_path in job["output_files"]:
            path = Path(file_path)
            if path.exists():
                path.unlink()
    
    # Delete job
    del jobs[job_id]
    
    return {"message": "Job deleted successfully"}


@app.post("/api/generate-from-scenes")
async def generate_from_scenes(
    request: SceneRequest,
    background_tasks: BackgroundTasks
):
    """Generate comic from pre-defined scenes."""
    config = get_config()
    
    if request.llm_provider == "groq" and not config.groq_api_key:
        raise HTTPException(status_code=400, detail="Groq API key not configured")
    elif request.llm_provider == "gemini" and not config.google_api_key:
        raise HTTPException(status_code=400, detail="Google API key not configured")
    
    # Create job
    job_id = str(uuid.uuid4())
    create_job(job_id, "Scene-based comic generation started")
    
    # Convert scene dicts to Scene objects
    def generate_from_scenes_task(job_id: str, scenes_data: List[dict], style: str, 
                                   add_dialogue: bool, llm_provider: str):
        try:
            update_job(job_id, status="processing", message="Processing scenes...")
            
            crafter = ComicCrafter(llm_provider=llm_provider)
            
            scenes = [Scene(**scene_data) for scene_data in scenes_data]
            
            output_paths = crafter.generate_from_scenes(
                scenes=scenes,
                style=style,
                add_dialogue=add_dialogue,
                output_name=f"comic_{job_id[:8]}"
            )
            
            output_files = [str(path) for path in output_paths]
            
            update_job(
                job_id,
                status="completed",
                message="Comic generation completed",
                completed_at=datetime.now().isoformat(),
                output_files=output_files
            )
        except Exception as e:
            update_job(
                job_id,
                status="failed",
                message="Generation failed",
                completed_at=datetime.now().isoformat(),
                error=str(e)
            )
    
    background_tasks.add_task(
        generate_from_scenes_task,
        job_id=job_id,
        scenes_data=request.scenes,
        style=request.style,
        add_dialogue=request.add_dialogue,
        llm_provider=request.llm_provider
    )
    
    return {"job_id": job_id, "message": "Scene-based generation started"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
