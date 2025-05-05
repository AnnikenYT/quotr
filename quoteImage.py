from PIL import Image, ImageDraw, ImageFont
import textwrap
import asyncio

async def add_text_to_gif(gif_path, output_path, text):
    # Open the GIF
    gif = await asyncio.to_thread(Image.open, gif_path)
    frames = []
    font_size = 30
    font_path = "./assets/font.ttf"  # Adjust if needed

    try:
        font = await asyncio.to_thread(ImageFont.truetype, font_path, font_size)
    except IOError:
        raise Exception("Font file not found. Please check the font path.")

    for frame in range(gif.n_frames):
        await asyncio.to_thread(gif.seek, frame)
        frame_image = await asyncio.to_thread(gif.convert, "RGBA")
        draw = ImageDraw.Draw(frame_image)

        # Text wrapping or scaling
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
        max_width = frame_image.width - 20  # Padding
        if text_width > max_width:
            wrapped_text = textwrap.fill(text, width=20, break_long_words=False, break_on_hyphens=False)
        else:
            wrapped_text = text

        # Recalculate text dimensions after wrapping
        text_bbox = draw.textbbox((0, 0), wrapped_text, font=font)
        text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]

        # Calculate text position (centered)
        x = (frame_image.width - text_width) // 2
        y = (frame_image.height - text_height) // 2

        # Draw text outline (orange)
        outline_range = 2
        for dx in range(-outline_range, outline_range + 1):
            for dy in range(-outline_range, outline_range + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), wrapped_text, font=font, fill="orange", align="center")

        # Draw text (white)
        draw.text((x, y), wrapped_text, font=font, fill="white", align="center")

        frames.append(frame_image)

    # Save the modified GIF
    await asyncio.to_thread(
        frames[0].save,
        output_path,
        save_all=True,
        append_images=frames[1:],
        loop=gif.info.get("loop", 0),
        duration=gif.info.get("duration", 100),
    )

# Example usage
if __name__ == "__main__":
    text = '''
    "Ihr habt mommy issues" - Ich
"das sind keine issues das ist die lösung" - Jonathan'''
    asyncio.run(add_text_to_gif("assets/background.gif", "output.gif", text))
