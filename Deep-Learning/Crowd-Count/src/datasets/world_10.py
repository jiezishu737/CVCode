# --------------------------------------------------------
# WorldExpo Dataset
# Copyright (c) 2018 Fudan-VTS
# Licensed under The MIT License [see LICENSE for details]
# Written by liwenxi
# --------------------------------------------------------
import numpy as np
from scipy.io import loadmat
import glob
import torch
import h5py
from torch.utils.data import Dataset
from skimage import io, color
import os, scipy
import cv2
import threading
from torchvision import transforms


def gaussian_filter_density(gt, pts):
    density = np.zeros(gt.shape, dtype=np.float32)
    gt_count = len(pts)
    if gt_count == 0:
        return density
    for i, pt in enumerate(pts):
        pt2d = np.zeros(gt.shape, dtype=np.float32)
        pt2d[min(int(round(pt[1])), gt.shape[0]-1), min(int(round(pt[0])), gt.shape[1]-1)] = 1.
        if gt_count > 1:
            sigma = 3
        else:
            sigma = np.average(np.array(gt.shape))/2./2. #case: 1 point
        density += scipy.ndimage.filters.gaussian_filter(pt2d, sigma, mode='constant')
    return density

def extract_gt_thread(img_path, point_path, img_list, start, end):
    for idx in range(start, end):
        image = io.imread(img_list[idx])
        gray = color.rgb2gray(image)
        read_path = point_path + img_list[idx].split('/')[-1][:6] + '/' \
                    + img_list[idx].split('/')[-1].replace('.jpg', '.mat')
        input = open(read_path, 'rb')
        check = float(str(input.read(10)).split('\'')[1].split(' ')[1])
        input.close()
        if check == 7.3:
            points = np.array(h5py.File(read_path, 'r')['point_position'])
            points = points.transpose()
        else:
            points = loadmat(read_path)['point_position']

        density = gaussian_filter_density(gray, points)
        np.save(img_path+'ground_truth/'+img_list[idx].split('/')[-1].replace('.jpg', ''), density)


def extract_gt(img_path, point_path, img_list):
    #use multi-thread
    os.mkdir(img_path+'ground_truth/')
    threads = []
    t1 = threading.Thread(target=extract_gt_thread, args=(img_path, point_path, img_list, 0, 500))
    threads.append(t1)
    t2 = threading.Thread(target=extract_gt_thread, args=(img_path, point_path, img_list, 500, 1000))
    threads.append(t2)
    t3 = threading.Thread(target=extract_gt_thread, args=(img_path, point_path, img_list, 1000, 1500))
    threads.append(t3)
    t4 = threading.Thread(target=extract_gt_thread, args=(img_path, point_path, img_list, 1500, 2000))
    threads.append(t4)
    t5 = threading.Thread(target=extract_gt_thread, args=(img_path, point_path, img_list, 2000, 2500))
    threads.append(t5)
    t6 = threading.Thread(target=extract_gt_thread, args=(img_path, point_path, img_list, 2500, 3000))
    threads.append(t6)
    t7 = threading.Thread(target=extract_gt_thread, args=(img_path, point_path, img_list, 3000, len(img_list)))
    threads.append(t7)

    for t in threads:
        # t.setDaemon(True)
        t.start()
    for t in threads:
        t.join()


class WorldExpoDataset(Dataset):
    def __init__(self, img_path, point_path, data_type = 'RGB', transform=None):
        self.img_path = img_path
        self.point_path = point_path
        self.data_type = data_type
        self.transform = transform
        wrong_data = ['200778_C10-03-S20100717083000000E20100717233000000_4_clip1_2.jpg',
                      '200778_C10-03-S20100717083000000E20100717233000000_4_clip1_3.jpg',
                      '200778_C10-03-S20100717083000000E20100717233000000_clip1_3.jpg',
                      '500674_E05-03-S20100717083000000E20100717233000000_5_clip1_2.jpg',
                      '600079_E06-02-S20100717083000000E20100717233000000_7_clip1_2.jpg',
                      '100270_A02HiRD36-01-S20100626080000000E20100626233000000_new.split.157_2.jpg']
        for i in range(len(wrong_data)):
            if os.path.exists(self.img_path + wrong_data[i]):
                os.remove(self.img_path + wrong_data[i])
        self.img_list = glob.glob(self.img_path + '*.jpg')

        if not os.path.exists(self.img_path + 'ground_truth/'):
            print("Start extract")
            extract_gt(self.img_path, self.point_path, self.img_list)
            print("Finish extract")
        else:
            print("Already extract")

    def __len__(self):
        return len(self.img_list)

    def __getitem__(self, idx):
        if self.data_type == 'RGB':
            image = io.imread(self.img_list[idx])
        elif self.data_type == 'flow':
            image = np.load(self.img_path + 'flow/' + self.img_list[idx].split('/')[-1].replace('.jpg', '.npy'))
        else:
            image = io.imread(self.img_list[idx])
            flow = np.load(self.img_path + 'flow/' + self.img_list[idx].split('/')[-1].replace('.jpg', '.npy'))

        density = np.load(self.img_path + 'ground_truth/' + self.img_list[idx].split('/')[-1].replace('.jpg', '.npy'))
        density = roi(density, self.point_path, self.img_list[idx])
        density = cv2.resize(density, (0, 0), fx=0.125, fy=0.125, interpolation=cv2.INTER_CUBIC)*64

        # numpy_array
        density = torch.tensor(density)
        density = torch.unsqueeze(density, 0)
        image = roi(image, self.point_path, self.img_list[idx])
        if self.transform is not None:
            image = self.transform(image)
            image = torch.tensor(image)
            if self.data_type == 'all':
                flow = roi(flow, self.point_path, self.img_list[idx])
                flow = self.transform(flow)
                flow = torch.tensor(flow)
        else:
            image = torch.tensor(image)
            image = image.permute(2, 0, 1)
            if self.data_type == 'all':
                flow = roi(flow, self.point_path, self.img_list[idx])
                flow = torch.tensor(flow)
                flow = flow.permute(2, 0, 1)
        #  return: torch.Size([3, 576, 720]) torch.Size([1, 576, 720])
        if self.data_type == 'all':
            return image, flow, density
        return image, density


class WorldExpoTestDataset(Dataset):
    def __init__(self, img_path, point_path, transform=None, data_type='RGB', type='scene1'):
        # type  'scene1'|'scene2'|'scene3'|'scene4'|'scene5'
        self.img_path = img_path
        self.point_path = point_path
        self.data_type = data_type
        self.type = type
        self.transform = transform
        if type is 'scene1':
            self.subdir = '104207/'
        elif type is 'scene2':
            self.subdir = '200608/'
        elif type is 'scene3':
            self.subdir = '200702/'
        elif type is 'scene4':
            self.subdir = '202201/'
        elif type is 'scene5':
            self.subdir = '500717/'
        else:
            return 1
        wrong_data = ['104207/104207_1-04-S20100821071000000E20100821120000000_034550.jpg']
        for i in range(len(wrong_data)):
            if os.path.exists(self.img_path + wrong_data[i]):
                os.remove(self.img_path + wrong_data[i])
        self.img_list = glob.glob(self.img_path + self.subdir + '*.jpg')
        if not os.path.exists(self.img_path+self.subdir + 'ground_truth/'):
            print("Start extract")
            os.mkdir(self.img_path + self.subdir+'ground_truth/')
            extract_gt_thread(self.img_path+self.subdir, self.point_path, self.img_list, 0, len(self.img_list))
            print("Finish extract")
        else:
            print("Already extract")

    def __len__(self):
        return len(self.img_list)

    def __getitem__(self, idx):
        if self.data_type == 'RGB':
            image = io.imread(self.img_list[idx])
        elif self.data_type == 'flow':
            image = np.load(self.img_path + 'flow/' + self.img_list[idx].split('/')[-1].replace('.jpg', '.npy'))
        else:
            image = io.imread(self.img_list[idx])
            flow = np.load(self.img_path + 'flow/' + self.img_list[idx].split('/')[-1].replace('.jpg', '.npy'))
        # read_path = self.point_path + self.subdir + self.img_list[idx].split('/')[-1].replace('.jpg', '.mat')
        # input = open(read_path, 'rb')
        # check = float(str(input.read(10)).split('\'')[1].split(' ')[1])
        # input.close()
        # if check == 7.3:
        #     points = np.array(h5py.File(read_path, 'r')['point_position'])
        #     points = points.transpose()
        # else:
        #     points = loadmat(read_path)['point_position']

        # count = [len(points)]
        # # count type: torch.Size([1])
        # count = torch.tensor(count, dtype=torch.double)
        density = np.load(self.img_path + self.subdir+'ground_truth/' + self.img_list[idx].split('/')[-1].replace('.jpg', '.npy'))
        density = roi(density, self.point_path, self.img_list[idx])
        # density = cv2.resize(density, (0, 0), fx=0.125, fy=0.125, interpolation=cv2.INTER_CUBIC)*64

        # numpy_array to tensor
        density = torch.tensor(density)
        count = torch.sum(density).unsqueeze(0)

        image = roi(image, self.point_path, self.img_list[idx])
        # numpy_array
        if self.transform is not None:
            image = self.transform(image)
            # print(type(image))
            image = torch.tensor(image)
            if self.data_type == 'all':
                flow = roi(flow, self.point_path, self.img_list[idx])
                flow = self.transform(flow)
                flow = torch.tensor(flow)
        else:
            image = torch.tensor(image)
            image = image.permute(2, 0, 1)
            if self.data_type == 'all':
                flow = roi(flow, self.point_path, self.img_list[idx])
                flow = torch.tensor(flow)
                flow = flow.permute(2, 0, 1)
        # return：torch.Size([3, 576, 720]) torch.Size([1, 576, 720])
        if self.data_type == 'all':
            return image, flow, count
        return image, count


def average_scene(scene1, scene2, scene3, scene4, scene5):
    return (scene1 + scene2 + scene3 + scene4 + scene5) / 5

def roi(image, point_path, img_list):
    read_path = point_path + img_list.split('/')[-1][:6] + '/' \
                + 'roi.mat'
    input = open(read_path, 'rb')
    check = float(str(input.read(10)).split('\'')[1].split(' ')[1])
    input.close()
    if check == 7.3:
        x = np.array(h5py.File(read_path, 'r')['maskVerticesXCoordinates'])
        x = x.transpose()
        y = np.array(h5py.File(read_path, 'r')['maskVerticesYCoordinates'])
        y = y.transpose()
        points = np.concatenate((x, y), axis=1)
        points = points[np.newaxis, :, :]
    else:
        x = loadmat(read_path)['maskVerticesXCoordinates']
        y = loadmat(read_path)['maskVerticesYCoordinates']

        points = np.concatenate((x, y), axis=1)
        points = points[np.newaxis, :, :]

    points = np.array(points, dtype=np.int32)

    im = np.zeros(image.shape[:2], dtype="uint8")
    cv2.polylines(im, points, True, 255)
    cv2.fillPoly(im, points, 255)

    masked = cv2.bitwise_and(image, image, mask=im)

    return masked


if __name__ == "__main__":
    img_path = "./world_expo/train_frame/"
    point_path = './world_expo/train_label/'
    data = WorldExpoDataset(img_path, point_path)


    # img_path = "./world_expo/test_frame/"
    # point_path = './world_expo/test_label/'
    # data = WorldExpoTestDataset(img_path, point_path, 'scene1')