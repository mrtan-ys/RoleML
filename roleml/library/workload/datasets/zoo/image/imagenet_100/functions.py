from torchvision import transforms


_MEAN = (0.485, 0.456, 0.406)
_STD = (0.229, 0.224, 0.225)

default_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(_MEAN, _STD),
])
