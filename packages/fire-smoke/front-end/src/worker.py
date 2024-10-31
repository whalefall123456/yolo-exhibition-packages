import time

import cv2
import numpy as np
import torch
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QFileDialog
from ultralytics import YOLO
from collections import defaultdict
import os
import utils.draw_boxes as Boxes
import utils.statistics_classes as Statistics

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
np.set_printoptions(suppress=True)


class Worker(QThread):
    send_img = pyqtSignal(np.ndarray)  # 检测结果图像
    send_raw = pyqtSignal(np.ndarray)  # 检测源图像
    send_statistic = pyqtSignal(dict)  # 检测结果统计信息

    send_msg = pyqtSignal(str)  # 日志
    send_fps = pyqtSignal(str)  # 帧率

    def __init__(self):
        super(Worker, self).__init__()
        self.source = None
        self.model_path = None
        self.model = None
        self.conf = None
        self.iou = None
        self.classes = None

        self.jump_out = False
        self.is_continue = True

    def run(self):
        try:
            if self.source is None:
                print('请上传文件')
                return
            self.detect_video(video_path=self.source, save_path='')
        except Exception as e:
            self.send_msg.emit('%s' % e)

    def load_model(self, model_path):
        if model_path:
            self.model_path = model_path

    def get_classes(self):
        if self.model_path is not None:
            model = self.init_model(self.model_path)
            names = model.module.names if hasattr(model, 'module') else model.names  # 分类信息
            del model
            return names
        else:
            return []

    def init_model(self, model_path):
        if model_path:
            model = YOLO(model_path)
            self.model = model.to(device)
            return model
        return False

    def detect_image(self, images):
        model = self.init_model(self.model_path)
        results = model.predict(images)
        return results

    def detect_video(self, video_path, save_path):
        cap = cv2.VideoCapture(video_path)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(round(cap.get(cv2.CAP_PROP_FPS)))
        if fps == 0:
            fps = 20.0  # 如果无法获取帧率，则设置为默认值

        model = self.init_model(self.model_path)
        video_frame = 0
        average_fps = 0.0
        try:
            while True:
                success, frame = cap.read()
                print('视频帧获取是否成功：{}'.format(success))
                if success:
                    start = time.time()

                    conf = self.conf if self.conf else 0.3
                    iou = self.iou if self.iou else 0.7
                    classes = self.classes if self.classes else None

                    names = model.module.names if hasattr(model, 'module') else model.names  # 分类信息

                    results = model.predict(frame, conf=conf, iou=iou, classes=classes)  # 检测

                    end = time.time()
                    video_frame = video_frame + 1
                    video_fps = 1.0 / (end - start)
                    average_fps += video_fps

                    print('当前帧：{}'.format(video_frame))
                    print("平均帧率: %.1f" % (average_fps / video_frame))

                    Boxes.draw_boxes(frame, results)
                    classes = Statistics.statistics_classes(results, names)

                    self.send_img.emit(frame if isinstance(frame, np.ndarray) else frame[0])
                    self.send_statistic.emit(classes)

                    if 0xFF == ord("q"):
                        break
                else:
                    print('结束了')
                    break
            cap.release()
            cv2.destroyAllWindows()
        except Exception as e:
            print(e)

    def set_source(self, source):
        self.source = source

    def set_model_path(self, model_path):
        self.model_path = model_path if model_path else None

    def set_classes(self, classes):
        self.classes = classes if len(classes) > 0 else None