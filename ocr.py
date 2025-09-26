import json
import http.client, urllib.request, urllib.parse, urllib.error
import os
import time
import aiohttp
import asyncio
import logging

# API_KEY =  os.environ['api_key']#"cc4cae2ff9b549398d002398edc3e07b"
# ENDPOINT = os.environ['urlvision']#"https://xtvision.cognitiveservices.azure.com/"

API_KEY =  "cc4cae2ff9b549398d002398edc3e07b"
ENDPOINT = "https://xtvision.cognitiveservices.azure.com/"

# Define thresholds for grouping
vertical_threshold = 80  # Max vertical distance for lines in the same paragraph/neighbor group
horizontal_threshold = 120  # Maximum horizontal distance between lines in the same group
stamp_vertical_threshold = 5
from logger_config import logger, traceid_var

# logger = logging.getLogger(__name__)

def azure_to_opencv_bbox(azure_bbox):
    # Extract the x and y coordinates
    x_coords = azure_bbox[0::2]  # Get every second element starting at 0 (x1, x2, x3, x4)
    y_coords = azure_bbox[1::2]  # Get every second element starting at 1 (y1, y2, y3, y4)

    # Calculate the top-left corner coordinates
    x_min = min(x_coords)
    y_min = min(y_coords)

    # Calculate width and height
    width = max(x_coords) - x_min
    height = max(y_coords) - y_min

    # Return the OpenCV bounding box [x, y, w, h]
    return [round(x_min*300), round(y_min*300), round(width*300), round(height*300)]

# Helper function to merge two bounding boxes
def merge_bounding_boxes(box1, box2):
    x_min = min(box1[0], box2[0])
    y_min = min(box1[1], box2[1])
    x_max = max(box1[0] + box1[2], box2[0] + box2[2])
    y_max = max(box1[1] + box1[3], box2[1] + box2[3])
    return [x_min, y_min, x_max - x_min, y_max - y_min]

# # Helper function to determine if boxes are on the same line
def are_on_same_line_threshold(box1, box2, v_threshold):
    bottom1 = box1[1] + box1[3]
    bottom2 = box2[1] + box2[3]
    return abs(box1[1] - box2[1]) < v_threshold or abs(bottom1 - bottom2) < v_threshold

# # Helper function to check if two boxes are aligned (left or right)
def are_aligned_threshold(box1, box2, h_threshold):
    return abs(box1[0] - box2[0]) < h_threshold

# Process left and right side elements individually
def process_side_group(text_elements, current_side_group,vertical_threshold,horizontal_threshold):
    for element in text_elements:
        current_box = element['boundingBox']
        
        if (current_side_group and 
            (are_on_same_line_threshold(current_side_group[-1]['boundingBox'], current_box, vertical_threshold) or
             (are_aligned_threshold(current_side_group[-1]['boundingBox'], current_box, horizontal_threshold) and
              abs(current_side_group[-1]['boundingBox'][1] + current_side_group[-1]['boundingBox'][3] - current_box[1]) < vertical_threshold * 2))):
            current_side_group[-1]['line'].append(element['line'])
            current_side_group[-1]['boundingBox'] = merge_bounding_boxes(current_side_group[-1]['boundingBox'], current_box)
        else:
            current_side_group.append({'line': [element['line']], 'boundingBox': current_box})

    return current_side_group

# Helper function to determine if boxes are on the same line
def are_on_same_line(box1, box2):
    bottom1 = box1[1] + box1[3]
    bottom2 = box2[1] + box2[3]
    return abs(box1[1] - box2[1]) < 3 or abs(bottom1 - bottom2) < 3

# Helper function to check if two boxes are aligned (left or right)
def are_aligned(box1, box2):
    return abs(box1[0] - box2[0]) < 2

# Process left and right side elements individually
def process_same_line(text_elements, current_side_group):
    for element in text_elements:
        current_box = element['boundingBox']
        
        if (current_side_group and 
            (are_on_same_line(current_side_group[-1]['boundingBox'], current_box) or
             (are_aligned(current_side_group[-1]['boundingBox'], current_box) and
              abs(current_side_group[-1]['boundingBox'][1] + current_side_group[-1]['boundingBox'][3] - current_box[1]) < 4))):
            current_side_group[-1]['line'].append(element['line'])
            current_side_group[-1]['boundingBox'] = merge_bounding_boxes(current_side_group[-1]['boundingBox'], current_box)
        else:
            current_side_group.append({'line': [element['line']], 'boundingBox': current_box})

    return current_side_group
# Function to check if two bounding boxes overlap
def do_boxes_overlap(box1, box2):
    return not (box1[0] > box2[0] + box2[2] or  # box1 is right to box2
                box1[0] + box1[2] < box2[0] or  # box1 is left to box2
                box1[1] > box2[1] + box2[3] or  # box1 is below box2
                box1[1] + box1[3] < box2[1])    # box1 is above box2

# Function to merge overlapping bounding boxes within a group
def merge_overlapping_boxes(grouped_elements):
    merged_group = []
    while grouped_elements:
        current_element = grouped_elements.pop(0)
        current_box = current_element['boundingBox']
        merged = False
        for merged_element in merged_group:
            if do_boxes_overlap(merged_element['boundingBox'], current_box):
                merged_element['line'] += current_element['line'] # Merge lines
                merged_element['boundingBox'] = merge_bounding_boxes(merged_element['boundingBox'], current_box) # Merge bounding boxes
                merged = True
                break
        if not merged:
            merged_group.append(current_element)
    return merged_group



def merge_group_box(box, max_y, max_x):
	if not  box:
		return [],[]
	text_elements = box
	text_elements.sort(key=lambda x:x['boundingBox'][1])

	new_text_elements = [item for item in  text_elements if item['boundingBox'][1] < round(max_y/2.5) or   item['boundingBox'][1] > max_y-round(max_y/2.5)]
	middle_text_elemets = [item for item in  text_elements if item['boundingBox'][1] > round(max_y/2.5) and   item['boundingBox'][1] < max_y-round(max_y/2.5)]
	middle_same_line = process_same_line(middle_text_elemets, [])

	page_width = max([el['boundingBox'][0] + el['boundingBox'][2] for el in new_text_elements])
	middle_of_page = page_width / 2
	# # Separate elements into left and right based on middle_of_page
	left_elements = [el for el in new_text_elements if el['boundingBox'][0] < middle_of_page]
	right_elements = [el for el in new_text_elements if el['boundingBox'][0] >= middle_of_page]

	# # Sort the elements within each side by vertical position
	left_elements.sort(key=lambda x: x['boundingBox'][1])
	right_elements.sort(key=lambda x: x['boundingBox'][1])

	# Group left and right side elements based on vertical/horizontal threshold
	left_side_group = process_side_group(left_elements, [],stamp_vertical_threshold,horizontal_threshold)
	right_side_group = process_side_group(right_elements, [],stamp_vertical_threshold,horizontal_threshold)
	all_side_groups = right_side_group + left_side_group + middle_same_line
	# all_side_groups.sort(key=lambda x:x['boundingBox'][1])
	combined_group = merge_overlapping_boxes(all_side_groups)
	# combined_group.sort(key=lambda x:x['boundingBox'][1])
	stamplines = [{"line":" ".join(group['line']),"boundingBox": group['boundingBox']} for group in combined_group]
	return stamplines

async def call_vision(content):
    headers = {
        'Content-Type': 'application/octet-stream',
        'Ocp-Apim-Subscription-Key': API_KEY,
    }
    params = urllib.parse.urlencode({'language': 'en'})
    
    timeout = aiohttp.ClientTimeout(total=90)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            url = f'https://centralindia.api.cognitive.microsoft.com/vision/v3.2/read/analyze?{params}'
            async with session.post(url, data=content, headers=headers) as response:
                if response.status != 202:  # Accepted
                    logger.error(f"OCR API error: {response.status}")
                    return []
                    
                operation_location = response.headers['operation-location']
                operationId = operation_location.split("/")[-1]
                
                status_url = f'https://centralindia.api.cognitive.microsoft.com/vision/v3.2/read/analyzeResults/{operationId}'
                headers = {'Ocp-Apim-Subscription-Key': API_KEY}
                
                max_retries = 2
                retry_count = 0
                backoff_seconds = 2
                while retry_count < max_retries:
                    await asyncio.sleep(backoff_seconds)
                    try:
                        async with session.get(status_url, headers=headers) as status_response:
                            if status_response.status != 200:
                                logger.error(f"Error checking OCR status: {status_response.status}")
                                retry_count += 1
                                backoff_seconds = min(backoff_seconds + 1, 5)
                                continue
                                
                            data = await status_response.json()
                            if data["status"] == "succeeded":
                                all_pages = []
                                for text_result in data["analyzeResult"]["readResults"]:
                                    page_boxes = []
                                    __lines = text_result.get("lines", [])
                                    max_y = round(text_result.get("height", 0) * 300)
                                    max_x = round(text_result.get("width", 0) * 300)
                                    for line in __lines:
                                        _box = azure_to_opencv_bbox(line["boundingBox"])
                                        if _box:
                                            page_boxes.append({
                                                "line": line["text"],
                                                "boundingBox": _box
                                            })
                                    all_pages.append(page_boxes)
                                return all_pages
                            elif data["status"] == "failed":
                                logger.error(f"OCR operation failed: {data.get('recognitionError', 'Unknown error')}")
                                return []
                            
                            retry_count += 1
                            backoff_seconds = min(backoff_seconds + 1, 5)
                    except asyncio.TimeoutError:
                        logger.error("Timeout while polling OCR status endpoint")
                        return []
                    except aiohttp.ClientError as ce:
                        logger.error(f"Connection error while polling OCR status endpoint: {ce}")
                        return []
                logger.error("Maximum OCR polling retries reached")
                return []
                
        except asyncio.TimeoutError:
            logger.error("Timeout during OCR processing")
            return []
        except aiohttp.ClientError as ce:
            logger.error(f"OCR processing connection error: {ce}")
            return []
        except Exception as e:
            logger.error(f"OCR processing error: {e}")
            return []

                
        except asyncio.TimeoutError:
            logger.error("Timeout during OCR processing")
            return ""
        except aiohttp.ClientError as ce:
            logger.error(f"OCR processing connection error: {ce}")
            return ""
        except Exception as e:
            logger.error(f"OCR processing error: {e}")
            return ""
