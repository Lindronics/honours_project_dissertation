import random
import numpy as np
import cv2
from itertools import count
from collections import defaultdict
from sklearn.model_selection import train_test_split
import tensorflow as tf
import tensorflow.keras as K


transformation = np.array([
    [1.202290, -0.026808, -50.528589],
    [0.017762, 1.203090, -73.950204],
])

class Dataset(K.utils.Sequence):
    """
    Dataset loader for Keras model.
    """

    def __init__(self, metadata:str, rgb_only:bool=False, res:tuple=(480, 640), register:bool=True, batch_size:int=16, split:bool=False, train:bool=True):
        """
        Params
        ------
        metadata: str
            Path to file containing annotations
        rgb_only: bool
            Whether to load RGB images only and skip LWIR images
        res: tuple
            Target resolution of images
        register: bool
            Whether to transform RGB images to align them with LWIR images
        batch_size: int
            Batch size
        split: bool
            Whether to split the data into train and test
        train: bool
            Whether to use the train or test portion of the data if split is set
        """

        self.rgb_only = rgb_only
        self.res = res
        self.register = register
        self.batch_size = batch_size

        self.classes = defaultdict(count().__next__)
        self.samples = []

        samples = []
        labels = []
        with open(metadata, "r") as f:
            for line in f:
                line = line.split()
                class_label = self.classes[line[-1]]
                samples.append(tuple(line[:2] + [class_label]))
                labels.append(class_label)

        if split:
            train_data, test_data = train_test_split(samples, stratify=labels, test_size=0.2, random_state=42)
            self.samples = train_data if train else test_data
            pass
        else:
            random.seed(42)
            random.shuffle(samples)
            self.samples = samples

        self.class_dict = {key: val for val, key in self.classes.items()}
        self.class_labels = [val for key, val in sorted(self.class_dict.items())]


    def __len__(self) -> int:
        """ Returns the number of batches """
        return len(self.samples) // self.batch_size


    def load(self, path:str, register:bool=False) -> np.ndarray:
        """
        Loads an image at a given file path.

        Params
        ------
        path: str
            Path of the image
        register: bool
            Whether to apply affine transformation to image

        Returns
        -------
        The loaded image as a ndarray
        """
        img = tf.io.read_file(path)
        img = tf.image.decode_jpeg(img, channels=3)
        img = tf.image.convert_image_dtype(img, tf.float32).numpy()
        # img = cv2.imread(path) / 255
        if register:
            img = cv2.resize(img, (480, 640))
            img = cv2.warpAffine(img, transformation, (480, 640))
        img = cv2.resize(img, self.res)
        return img


    def __getitem__(self, idx:int) -> tuple:
        """
        Loads a batch of data.

        Params
        ------
        idx: int
            Index of the batch
        
        Returns
        -------
        Tuple containing the batch image tensor and the one-hot labels
        """
        if idx < self.__len__():
            X = []
            y = []
            for i in range(self.batch_size):
                rgb_path, lwir_path, label = self.samples[idx * self.batch_size + i]

                one_hot = np.zeros(self.num_classes())
                one_hot[label] = 1
                y.append(one_hot)

                rgb = self.load(rgb_path, register=self.register)

                if self.rgb_only:
                    X.append(rgb)
                else:
                    lwir = self.load(lwir_path, register=False)
                    lwir = np.mean(lwir, -1)[..., None]
                    stacked = np.dstack([rgb, lwir])
                    X.append(stacked)

            return np.array(X), np.array(y)
        else:
            raise StopIteration


    def get_all(self) -> tuple:
        """
        Loads the whole dataset.

        Returns
        ------
        A tensor (n_samples, height, width, channels) and a tensor (n_samples, n_classes)
        """
        X, y = [], []
        for i in range(len(self)):
            X_batch, y_batch = self.__getitem__(i)
            X.append(X_batch)
            y.append(y_batch)

        return np.concatenate(X, 0), np.concatenate(y, 0)


    def get_labels(self) -> np.ndarray:
        """ Gets a list of all labels """
        return np.array([sample[-1] for sample in self.samples])


    def num_classes(self) -> int:
        """ Gets the number of classes """
        return len(self.classes)


    def shape(self) -> tuple:
        """ Gets the tensor shape of a sample """
        return self.res[::-1] + tuple([(3 if self.rgb_only else 4)])
