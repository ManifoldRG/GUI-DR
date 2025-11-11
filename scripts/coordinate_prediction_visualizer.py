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
    # coordinate = (1479,503)
    coordinate = (479,491)

    # image_path = "outputs/run_20251108_185719_train/f4c21e9f-fbd7-4c45-a282-de06ae3b73c5_original/screenshots/step_1_click.png"
    # image_path = "outputs/run_20251108_185739_train/f4c21e9f-fbd7-4c45-a282-de06ae3b73c5/screenshots/step_1_click.png" # randomized

    # image_path = "outputs/run_20251111_002933_train/0ff1648e-28bb-4014-9b8a-3c050c25e334/screenshots/step_2_click.png"  #zoom 70%
    image_path = "outputs/run_20251111_002933_train/0c02c193-2aef-4817-92b4-56722edc6b57/screenshots/step_0_click.png"  #khol neutral

    # image_path = "outputs/run_20251111_003047_train/0a2130e7-1108-4281-8772-25c8671fb88e/screenshots/step_0_click.png"  #no zoom
    visualize_coordinate(coordinate, image_path)
