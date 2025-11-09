# Given a 2D coordinate and a image file path, visualize the coordinate on the image as a red cross

import matplotlib.pyplot as plt
from PIL import Image

def visualize_coordinate(coordinate: tuple, image_path: str):
    img = Image.open(image_path)
    plt.figure(figsize=(20, 10))
    plt.imshow(img)
    plt.scatter(coordinate[0], coordinate[1], color='red', marker='x', s=200)
    plt.savefig(f"experiments/{image_path.split('/')[-3]}.png")
    plt.show()
    

if __name__ == "__main__":
    coordinate = (996,440)
    # coordinate = (797,443)
    image_path = "outputs/run_20251108_185719_train/f4c21e9f-fbd7-4c45-a282-de06ae3b73c5_original/screenshots/step_1_click.png"
    # image_path = "outputs/run_20251108_185739_train/f4c21e9f-fbd7-4c45-a282-de06ae3b73c5/screenshots/step_1_click.png" # randomized
    visualize_coordinate(coordinate, image_path)
