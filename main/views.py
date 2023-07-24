from django.shortcuts import render
from django.http import HttpResponse, FileResponse
from PIL import Image
import requests
from io import BytesIO
import openai
import csv
import pandas as pd
import re
import io
from fuzzywuzzy import fuzz, process
from django.http import JsonResponse
import tempfile
from .forms import UploadFileForm
from io import StringIO
from django.views import View
from django.contrib import messages

# Create your views here.

openai.api_key = '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'

def index(request):
	return render(request,'main/index.html')

## OPENAI ##
def ai(request):
    if request.method == 'POST':
        url = request.POST['url']
        # Call OpenAI API to generate the product description using the URL
        # Replace YOUR_OPENAI_API_KEY with your actual OpenAI API key
        openai.api_key = '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'
        response = openai.Completion.create(
            engine='text-davinci-003',
            prompt=f"Generate a product description for the URL: {url}.",
            max_tokens=200,
            n=1,
            stop=None,
            temperature=0.7,
            top_p=None,
            frequency_penalty=0,
            presence_penalty=0
        )
        description = response.choices[0].text.strip()

        return render(request, 'main/ai.html', {'description': description})
    else:
        return render(request, 'main/ai.html')


## IMAGE RESIZER ##
def image_resize(request):
    if request.method == 'POST':
        try:
            image_url = request.POST.get('image_url')  # Get the image URL from the form input
            width = int(request.POST.get('width'))  # Get the desired width from the form input
            height = int(request.POST.get('height'))  # Get the desired height from the form input
            
            # Download the image from the URL
            response = requests.get(image_url)
            response.raise_for_status()  # Check if the request was successful
            
            # Open the downloaded image
            img = Image.open(BytesIO(response.content))
            
            # Resize the image
            img.thumbnail((width, height))
            
            # Save the resized image
            resized_image_path = 'resized_image.jpg'  # Choose a filename and extension for the resized image
            img.save(resized_image_path, optimize=True, quality=40)
            
            # Serve the resized image for download
            file_response = FileResponse(open(resized_image_path, 'rb'))
            file_response['Content-Disposition'] = 'attachment; filename="resized_image.jpg"'
            return file_response
        
        except (KeyError, requests.exceptions.RequestException, ValueError):
            return HttpResponseServerError("Failed to download and resize the image.")
    
    return render(request, 'main/image-resize.html')

# def inner(request):
#     return render(request,'main/inner-page.html')

## XML Sitemap Generator ##
def generate_sitemap(file_path):
    # Read the hreflang information from the CSV file
    hreflang_dict = {}
    with open(file_path, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # skip the header row
        for row in reader:
            url = row[0]
            lang = row[1]
            href = row[2]
            if url not in hreflang_dict:
                hreflang_dict[url] = {}
            hreflang_dict[url][lang] = href

    # Generate the XML sitemap
    with open('sitemap.xml', 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n')
        f.write('        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n')
        for url, hreflang_dict in hreflang_dict.items():
            f.write('    <url>\n')
            f.write(f'        <loc>{url}</loc>\n')
            for lang, href in hreflang_dict.items():
                f.write(f'        <xhtml:link rel="alternate" hreflang="{lang}" href="{href}" />\n')
            f.write('    </url>\n')
        f.write('</urlset>\n')

def upload_csv(request):
    if request.method == 'POST' and request.FILES['csv_file']:
        csv_file = request.FILES['csv_file']
        file_path = 'media/hreflang.csv'  # Set the desired file path to save the uploaded CSV file
        with open(file_path, 'wb+') as destination:
            for chunk in csv_file.chunks():
                destination.write(chunk)

        generate_sitemap(file_path)

        # Serve the generated sitemap CSV file for download
        with open('sitemap.xml', 'r') as f:
            response = HttpResponse(f, content_type='application/xml')
            response['Content-Disposition'] = 'attachment; filename=sitemap.xml'
            return response
    return render(request, 'main/xml.html')

## REDIRECT BUILDER ##
# create dataframe from the CSV file
def read_csv(file):
    print('Reading CSV...')
    df = pd.read_csv(file, encoding='utf-8-sig')
    df = df.astype(str)  # Convert all columns to string type
    return df

### Comment out preprocessing rules that are not required for each column

def preprocess_url1(url):
    # Preprocessing rules for the (source) first column
    #url = url.lower()  # force lowercase
    url = re.sub(r'^https?://', '', url)  # strips out protocol
    url = re.sub(r'^www\.', '', url)  # strips out www.
    url = re.sub(r'^https?://(www\.)?', '', url)  # strips out protocol and www.
    url = re.sub(r'^https?://[^/]+', '', url)  # remove domain name including protocol
    url = re.sub(r'\?.*$', '', url)  # removes parameters and querystrings
    # url = re.sub(r'/$', '', url) # removes trailing slash
    url = re.sub(r'\.(php|htm|html|asp)$', '', url)  # remove file extensions
    url = re.sub(r'\.(css|json|js)$', '', url)  # remove asset files
    url = re.sub(r'\.(webp|png|jpe?g|gif|bmp|svg|tiff?)$', '', url)  # remove image formats
    url = re.sub(
        r'\.(pdf|docx?|csv|xlsx?|pptx?|zip|rar|tar|gz|7z|mp3|wav|ogg|avi|mp4|mov|mkv|flv|wmv)$', '', url
    )  # Remove common download formats
    print('Preprocessing Source...')
    return url


def preprocess_url2(url):
    # Preprocessing rules for the (destination) second column
    url = url.lower()  # force lowercase
    url = re.sub(r'^https?://', '', url)  # strips out protocol
    url = re.sub(r'^www\.', '', url)  # strips out www.
    url = re.sub(r'^https?://(www\.)?', '', url)  # strips out protocol and www.
    url = re.sub(r'^https?://[^/]+', '', url)  # remove domain name including protocol
    url = re.sub(r'\?.*$', '', url)  # removes parameters and querystrings
    # url = re.sub(r'/$', '', url) # removes trailing slash
    url = re.sub(r'\.(php|htm|html|asp)$', '', url)  # remove file extensions
    url = re.sub(r'\.(css|json|js)$', '', url)  # remove asset files
    url = re.sub(r'\.(webp|png|jpe?g|gif|bmp|svg|tiff?)$', '', url)  # remove image formats
    url = re.sub(
        r'\.(pdf|docx?|csv|xlsx?|pptx?|zip|rar|tar|gz|7z|mp3|wav|ogg|avi|mp4|mov|mkv|flv|wmv)$', '', url
    )  # Remove common download formats
    url = re.sub(r'\?(page|pagenumber|start)=[^&]*(&|$)', '', url)  # ignore pagination URLs
    print('Preprocessing Destination...')
    return url


def get_best_match(url, url_list):
    print('Fuzzying URL...')
    scorers = [fuzz.token_sort_ratio, fuzz.token_set_ratio, fuzz.partial_token_sort_ratio]
    best_match_data = max(
        (process.extractOne(url, url_list, scorer=scorer) for scorer in scorers), key=lambda x: x[1]
    )
    best_match, best_score = best_match_data[0], best_match_data[1]
    print('URL Fuzzed...')
    return best_match, best_score


# threshold score is set at 60. URLs that do not meet threshold will need to be manually mapped
def compare_urls(df, column1, column2, threshold=60):
    result = []
    print('Adding more fuzz...')
    preprocessed_url1_list = [preprocess_url1(url) for url in df[column1]]
    preprocessed_url2_list = [preprocess_url2(url) for url in df[column2]]

    for url, preprocessed_url1 in zip(df[column1], preprocessed_url1_list):
        best_match, best_score = get_best_match(preprocessed_url1, preprocessed_url2_list)

        if best_score < threshold:
            best_match = 'No Match'

        result.append({'Source URL': url, 'Best Match Destination URL': best_match, 'Match Score': best_score})
    print('Fuzzy finished')
    return result


def compare_urls_in_csv(file, column1, column2):
    df = read_csv(file)
    result = compare_urls(df, column1, column2)
    result_df = pd.DataFrame(result)
    result_csv = result_df.to_csv(index=False)  # Convert DataFrame to CSV string

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="result.csv"'

    # Write the CSV string as the response content
    response.write(result_csv)
    return response


def redirect_builder_view(request):
    if request.method == 'POST':
        file = request.FILES['file']
        if file:
            file_content = file.read().decode('utf-8')
            csv_data = io.StringIO(file_content)
            response = compare_urls_in_csv(csv_data, "source", "destination")
            return response
    return render(request, 'main/redirect-builder.html')


def generate_product_subtitle_and_description(title, description):
    prompt = f"""
            You are a copywriter for LookFantastic. 
            Subtitles should be:
                A concise summary of the product – what it is and what it does
                16 words or less
                Doesn’t include the product name or brand name
                Example: A rich cleansing balm that melts away makeup to reveal soft, radiant-looking skin.
                Example: A lightweight daily sunscreen with SPF50+, suitable for sensitive skin types.
            Product Descriptions should be:
                50-100 words
                2-3 paragraphs
                What the product is, USPs, key ingredients and their benefits, summary

            You are capable of:
            Explaining and de-coding beauty jargon / ingredient benefits and
            technologies.
            Being clear and concise with an authoritative tone.
            Ensuring you avoid the use of humour and chatty/conversational tone. Maintain
            a professional tone.
            Accurate key ingredient research, highlighting benefits in a
            way that's easy to understand.
            Factual and informative language, rather than trying to over sell a product through excessive adjectives.
            And avoid terms such as heal, Repair, Treat, Irritation, Inflammation, Reduces Stress, Collagen Production, Acne
            Eczema, Youth-generating, Age-defying, Prevents premature ageing.
             
            When given a title and description of a product you are able to produce a new subtitle and description
            based on the above rules.
            Generate a new subtitle and description for the following product.
            Product Name: {title}\n Product Description: {description}\n"""

    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=256,
        n=1,
        stop=None,
        temperature=0.6,
    )
    generated_text = response.choices[0].text.strip()
    if "\n" in generated_text:
        subtitle, generated_description = generated_text.split("\n", 1)
    else:
        subtitle = generated_text
        generated_description = "No description generated."

    return subtitle, generated_description

class ProductDescUpload(View):
    def get(self, request):
        form = UploadFileForm()
        return render(request, 'main/product-descriptions.html', {'form': form})

    def post(self, request):
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            messages.info(request, "Your file has been uploaded and is being processed. This may take a few minutes. Please do not refresh the page.")
            # Read input CSV and generate new subtitle and description
            file = request.FILES['file']
            decoded_file = file.read().decode('cp1252').splitlines()
            reader = csv.DictReader(decoded_file)
            rows = list(reader)
            fieldnames = reader.fieldnames + ["new_subtitle", "new_description"]

            # Prepare the output CSV
            outfile = StringIO()
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()

            for row in rows:
                product_title = row["product title"]
                product_description = row["product description"]
                new_subtitle, new_description = generate_product_subtitle_and_description(product_title, product_description)
                row["new_subtitle"] = new_subtitle
                row["new_description"] = new_description
                writer.writerow(row)

            # Create the HttpResponse object with the appropriate CSV header.
            response = HttpResponse(outfile.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="output.csv"'

            return response
        else:
            return HttpResponseBadRequest('Invalid form')

    