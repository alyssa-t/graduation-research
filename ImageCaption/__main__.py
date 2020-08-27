import tensorflow as tf
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle

import re
import numpy as np
import os
import time
import json
import pickle
import warnings

import glob
from PIL import Image
from tqdm import tqdm
from .imageCaptioningDataset import Methods_Dataset
from .model import *
from .train import *
from .evaluate import *
from .preprocess import *
from .telegram_logger import telegramSendMessage

ANNOTATION_FILE = "captions_train2017_pt.txt"
ANNOTATION_FILE_PATH = "/"
TRAIN_IMAGE_FOLDER_PATH = "/"
VALIDATION_IMAGE_FOLDER_PATH = "/"
BATCH_SIZE_INCEPTIONV3 = 16
NUM_CAPTIONS = 30000
EXTRACT_NPY = False

BATCH_SIZE = 64
BUFFER_SIZE = 1000
EPOCHS = 40
TOP_K = 10000

CHECKPOINT_PATH = "./checkpoints/train/2-8-yolo-v.3"
TEST_IMAGE_PATH = "*.npy"

# Shape of the vector extracted from InceptionV3 is (64, 2048)
# These two variables represent that vector shape
features_shape = 2048
attention_features_shape = 64
#embeddingdim = vector dimension for word mapping
embedding_dim = 512
#units = dimensionality of the output space of models
units = 1024
# words vector size
vocab_size = TOP_K + 1
#num_setps = int division NUM=CAPTIONS/BATCH_SIZE. ex: 4//1.5 = 2
num_steps = NUM_CAPTIONS // BATCH_SIZE

def main(trainCaptions, img_name_vector):

    #Code for setup GPU
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    """
    gpu_devices = tf.config.experimental.list_physical_devices('GPU')
    for device in gpu_devices:
        tf.config.experimental.set_memory_growth(device, True)
    tf.compat.v1.enable_eager_execution()
    """

    #Load images and captions

    #Create model for extract features using InceptionV3
    image_features_extract_model = createInceptionModel()
    if (EXTRACT_NPY):
        print("extracting feature of training set")
        createNpyFile (img_name_vector,
                        image_features_extract_model,
                        BATCH_SIZE_INCEPTIONV3)
    #Tokenize captions
    cap_vector, maxLength, tokenizer = tokenizeCaptions(trainCaptions, TOP_K)

    #Create Dataset
    methodDataset = Methods_Dataset(img_name_vector,
                                    cap_vector,
                                    BATCH_SIZE,
                                    BUFFER_SIZE)

    dataset = methodDataset.createDataset()
    #Create encoder decoder model
    encoder = CNN_Encoder(embedding_dim)
    decoder = RNN_Decoder(embedding_dim, units, vocab_size)

    #Define Optimizer and loss_object
    optimizer = tf.keras.optimizers.Adam()
    loss_object = tf.keras.losses.SparseCategoricalCrossentropy(
        from_logits=True, reduction='none')

    #Define Checkpoints
    ckpt = tf.train.Checkpoint(encoder=encoder,
                                decoder=decoder,
                                optimizer = optimizer)
    ckpt_manager = tf.train.CheckpointManager(ckpt, CHECKPOINT_PATH, max_to_keep=5)

    #Load Checkpoint if exists
    start_epoch = 0
    """
    if ckpt_manager.latest_checkpoint:
        start_epoch = int(ckpt_manager.latest_checkpoint.split('-')[-1])*5
        # restoring the latest checkpoint in CHECKPOINT_PATH
        status = ckpt.restore(ckpt_manager.latest_checkpoint)
        print("Restored CheckPoint from" + ckpt_manager.directory)
        status.assert_existing_objects_matched()
    """
    
    # adding this in a separate cell because if you run the training cell
    # many times, the loss_plot array will be reset
    loss_plot = []
    for epoch in range(start_epoch, EPOCHS):
        telegramSendMessage("yolo no comeco do epoch "+str(epoch))
        start = time.time()
        total_loss = 0
        
        for (batch, (img_tensor, target)) in enumerate(dataset):
                            
            batch_loss, t_loss = train_step(img_tensor,
                                                target,
                                                encoder,
                                                decoder,
                                                loss_object,
                                                tokenizer,
                                                optimizer)
            total_loss += t_loss
            if batch % 100 == 0:
                print ('Epoch {} Batch {} Loss {:.4f}'.format(
                    epoch + 1, batch, batch_loss.numpy() / int(target.shape[1])))
        # storing the epoch end loss value to plot later
        loss_plot.append(total_loss / num_steps)
        
        if epoch % 5 == 0:
            ckpt_manager.save()
        

        print ('Epoch {} Loss {:.6f}'.format(epoch + 1,
                                                total_loss/num_steps))
        print ('Time taken for 1 epoch {} sec\n'.format(time.time() - start))
        telegramSendMessage("yolo no fim do epoch "+str(epoch)+" com erro "+str(total_loss/num_steps))

    plt.plot(loss_plot)
    plt.xlabel('Epochs')
    plt.ylabel('Loss')
    plt.title('Loss Plot')
    plt.savefig('loss_plot-ver-epoch40.png', bbox_inches='tight')
    path = TEST_IMAGE_PATH

    id_npy = 0
    """
    for c in range(20):
        print("Captioning image :")
        path = str(id_npy) + ".jpg.npy"
        print(path)
        for i in range(10):
            
            result = evaluate(path,
                                                maxLength,
                                                attention_features_shape,
                                                decoder,
                                                encoder,
                                                image_features_extract_model,
                                                tokenizer)
            print ('Prediction Caption:', ' '.join(result))
            # plot_attention(TEST_IMAGE_PATH, result, attention_plot)
        id_npy += 1
    """

    for npyfile in glob.glob("/*.npy"):
        print("Captioning image :")
        #path = str(id_npy) + ".jpg.npy"
        print(npyfile)
        for i in range(10):
            
            result = evaluate(npyfile,
                                                maxLength,
                                                attention_features_shape,
                                                decoder,
                                                encoder,
                                                image_features_extract_model,
                                                tokenizer)
            print ('Prediction Caption:', ' '.join(result))
            # plot_attention(TEST_IMAGE_PATH, result, attention_plot)
    
    print("======= VAL IMAGES =======")
    for npyfile in glob.glob("/*.npy"):
        print()
        print("Captioning image :")
        #path = str(id_npy) + ".jpg.npy"
        print(npyfile)
        for i in range(10):
            
            result = evaluate(npyfile,
                                                maxLength,
                                                attention_features_shape,
                                                decoder,
                                                encoder,
                                                image_features_extract_model,
                                                tokenizer)
            print ('Prediction Caption:', ' '.join(result))
            # plot_attention(TEST_IMAGE_PATH, result, attention_plot)
    
    


if __name__ == '__main__':
    warnings.simplefilter(action='ignore', category=FutureWarning)
    telegramSendMessage("loading captions")
    try:
        trainCaptions, img_name_vector = loadAnnotation(ANNOTATION_FILE_PATH+ANNOTATION_FILE,
                                                                TRAIN_IMAGE_FOLDER_PATH,
                                                                None)
        print(len(trainCaptions))
        telegramSendMessage(str(len(trainCaptions)) + " npy files loaded")

        """
        print("----------------embdim = 512------------------")
        print("----------------rnn_units = 1024------------------")
        print()
        print()
        print()
        main(trainCaptions, img_name_vector)
        """
        print("----------------embdim = 2048------------------")
        print("----------------rnn_units = 2048------------------ sem fc")
        embedding_dim = 2048
        units = 2048
        print()
        print()
        print()
        main(trainCaptions, img_name_vector)
        """
        print("----------------embdim = 1024------------------")
        print("----------------rnn_units = 2048------------------")
        embedding_dim = 1024
        units = 2048
        print()
        print()
        print()
        main(trainCaptions, img_name_vector)
        """
    except Exception as e:
        telegramSendMessage('Houve um erro de execução')
        telegramSendMessage(str(e))
    
