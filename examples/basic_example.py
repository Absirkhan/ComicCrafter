"""Basic example of using ComicCrafter to generate a comic from text."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import ComicCrafter
from comiccrafter import ComicCrafter

# Example story
EXAMPLE_STORY = """
A young detective named Sarah walks into her messy office at sunset. 
She finds a mysterious letter on her desk with no return address.

Sarah opens the letter carefully. Inside is a cryptic message: 
"The treasure is hidden where the shadows meet the light."

Intrigued, Sarah grabs her coat and magnifying glass. She heads out 
into the city streets as night falls.

At the old lighthouse by the harbor, Sarah discovers a hidden compartment. 
Inside is an ancient map with strange symbols.

Sarah smiles, knowing this is just the beginning of her adventure.
"""


def main():
    """Run the basic example."""
    print("=" * 60)
    print("ComicCrafter - Basic Example")
    print("=" * 60)
    
    # Check if API keys are configured
    if not os.getenv("GROQ_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        print("\n⚠️  Warning: No API keys found in environment!")
        print("Please copy .env.example to .env and add your API keys:")
        print("  - GROQ_API_KEY (for Llama 3.3)")
        print("  - GOOGLE_API_KEY (for Gemini)")
        print("  - HUGGINGFACE_TOKEN (for image generation)")
        return
    
    # Initialize ComicCrafter
    print("\n📚 Initializing ComicCrafter...")
    try:
        # Try Groq first, fallback to Gemini
        if os.getenv("GROQ_API_KEY"):
            crafter = ComicCrafter(llm_provider="groq")
            print("✓ Using Groq (Llama 3.3) for text generation")
        elif os.getenv("GOOGLE_API_KEY"):
            crafter = ComicCrafter(llm_provider="gemini")
            print("✓ Using Google Gemini for text generation")
        else:
            raise ValueError("No LLM API key configured")
        
        if os.getenv("HUGGINGFACE_TOKEN"):
            print("✓ Using HuggingFace for image generation")
        else:
            print("⚠️  Warning: No HuggingFace token found")
            print("   Image generation may fail or use limited models")
        
    except Exception as e:
        print(f"\n❌ Error initializing ComicCrafter: {e}")
        return
    
    # Display story
    print("\n📖 Story to convert:")
    print("-" * 60)
    print(EXAMPLE_STORY.strip())
    print("-" * 60)
    
    # Generate comic
    print("\n🎨 Generating comic... (this may take a few minutes)")
    print("   1. Decomposing story into scenes...")
    print("   2. Extracting characters...")
    print("   3. Generating image prompts...")
    print("   4. Planning layouts...")
    print("   5. Generating images and composing pages...")
    
    try:
        output_paths = crafter.generate_comic(
            story_text=EXAMPLE_STORY,
            style="comic book style, graphic novel art, detailed",
            max_scenes=5,
            add_dialogue=True,
            output_name="detective_story"
        )
        
        # Display results
        print("\n✅ Comic generation complete!")
        print(f"\n📁 Generated {len(output_paths)} page(s):")
        for i, path in enumerate(output_paths, 1):
            print(f"   {i}. {path}")
        
        print(f"\n💾 Output directory: {crafter.output_dir}")
        print("\n🎉 Done! Open the generated images to view your comic.")
        
    except Exception as e:
        print(f"\n❌ Error during comic generation: {e}")
        print("\nTroubleshooting tips:")
        print("  1. Verify your API keys are correct")
        print("  2. Check your internet connection")
        print("  3. Ensure you have enough API quota/credits")
        print("  4. Check the logs for detailed error messages")
        return


if __name__ == "__main__":
    main()
