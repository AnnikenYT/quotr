from PIL import Image, ImageDraw, ImageFont
import textwrap
import asyncio

def create_quote_image(quote, author=None, background_color="#7289da"):
    # Padding variables
    padding = 50
    text_padding = 30
    line_spacing = 15
    
    # Fonts
    bold_font = ImageFont.truetype("assets/ggsans-Bold.ttf", 24)
    regular_font = ImageFont.truetype("assets/ggsans-Normal.ttf", 24)
    text_color = "#ffffff"
    
    # Calculate text dimensions
    wrapped_text = []
    for line in quote.splitlines():
        wrapped_line = textwrap.fill(line, width=60)
        wrapped_text.append(wrapped_line)
    text_height = len(wrapped_text) * bold_font.size + (len(wrapped_text) - 1) * line_spacing
        
    author_text = f"- {author if author else '?'}"
    author_height = regular_font.size + line_spacing + 10
    total_height = text_height + author_height + text_padding * 2
    
    
    # Create the image
    image_width = 800
    image_height = total_height + padding * 2
    image = Image.new("RGB", (image_width, image_height), background_color)
    draw = ImageDraw.Draw(image)
    
    # Draw the rounded rectangle
    rect_x0 = padding
    rect_y0 = padding
    rect_x1 = image_width - padding
    rect_y1 = rect_y0 + total_height
    draw.rounded_rectangle([rect_x0, rect_y0, rect_x1, rect_y1], radius=20, fill="#1e2124")
    
    # Draw the quote text
    current_y = rect_y0 + text_padding
    for line in wrapped_text:  # wrapped_text is now a list of lines
        draw.text((rect_x0 + text_padding, current_y), line, font=bold_font, fill=text_color)
        current_y += bold_font.size * len(line.splitlines()) + line_spacing
    
    # Draw the author text
    author_x = rect_x1 - text_padding - regular_font.getlength(author_text)
    author_y = current_y
    draw.text((author_x, author_y), author_text, font=regular_font, fill=text_color)
    
    # Save the image
    image_path = f"temp/quote_{int(asyncio.get_event_loop().time())}.png"
    image.save(image_path)
    return image_path
    

if __name__ == "__main__":
    # Example usage
    quote = """
"Ich würd sagen up your ass" - Nina, okay, crazy statement
"dann würd ich sagen gerne" - Jonathan nein danke"""
    image_path = create_quote_image(quote, "John Doe")
    print(f"Quote image saved at: {image_path}")