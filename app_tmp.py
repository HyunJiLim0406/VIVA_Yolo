import os
from flask import Flask, url_for, render_template, Response, flash, request, redirect, session
from darkflow.net.build import TFNet
from facenet.src import facenet
from facenet.src.align import detect_face
from werkzeug.utils import secure_filename
from flask_cors import CORS, cross_origin
from PIL import Image
import logging
import cv2
import tensorflow as tf
import numpy as np
import pickle
import glob
from scipy import misc

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger('HELLO WORLD')



UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

#모델 넣는 부분
options = {"model": "/home/rohitner/tensorflow/darkflow/cfg/tiny-yolo-voc.cfg",
           "load": "/home/rohitner/tensorflow/darkflow/bin/tiny-yolo-voc.weights",
           "threshold": 0.1, "gpu": 0.8}
tfnet = TFNet(options)

#uploads 폴더의 jpg 파일을 모두 찾아서 images에 저장
images = glob.glob('uploads/*.jpg')
def detect_images:
    for fname in images:
        #여기서 이미지 처리하면 됨

#여기가 바운딩박스 생성하는 부분 같은데 무슨 코드인지는 잘 모르겠음. 일단 그대로 넣어놓음 수정 필요
def gen(camera):
    sess = tf.Session()
    with sess.as_default():
        pnet, rnet, onet = detect_face.create_mtcnn(sess, None)
        facenet.load_model('/home/rohitner/models/facenet/20180402-114759/20180402-114759.pb')
        images_placeholder = tf.get_default_graph().get_tensor_by_name("input:0")
        embeddings = tf.get_default_graph().get_tensor_by_name("embeddings:0")
        phase_train_placeholder = tf.get_default_graph().get_tensor_by_name("phase_train:0")

        classifier_filename_exp = '/home/rohitner/models/lfw_classifier.pkl'
        with open(classifier_filename_exp, 'rb') as infile:
            (model, class_names) = pickle.load(infile)
        print('Loaded classifier model from file "%s"' % classifier_filename_exp)

        minsize = 20 # minimum size of face
        threshold = [ 0.6, 0.7, 0.7 ]  # three steps's threshold
        factor = 0.709 # scale factor
        file_index = 0

        while True:
            success, img = camera.read()
            results = tfnet.return_predict(img)
            for result in results:
                cv2.rectangle(img,
                               (result["topleft"]["x"], result["topleft"]["y"]),
                               (result["bottomright"]["x"], result["bottomright"]["y"]),
                             (255, 0, 0), 4)
                text_x, text_y = result["topleft"]["x"] - 10, result["topleft"]["y"] - 10

                cv2.putText(img, result["label"], (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0, 255, 0), 2, cv2.LINE_AA)
            if img.ndim<2:
                print('Unable to align')
                continue
            if img.ndim == 2:
                img = facenet.to_rgb(img)
            img = img[:,:,0:3]
            bounding_boxes, _ = detect_face.detect_face(img, minsize, pnet, rnet, onet, threshold, factor)
            nrof_faces = bounding_boxes.shape[0]
            if nrof_faces>0:
                det = bounding_boxes[:,0:4]
                det_arr = []
                img_size = np.asarray(img.shape)[0:2]
                if nrof_faces>1:
                    if True:# args.detect_multiple_faces:
                        for i in range(nrof_faces):
                            det_arr.append(np.squeeze(det[i]))
                    else:
                        bounding_box_size = (det[:,2]-det[:,0])*(det[:,3]-det[:,1])
                        img_center = img_size / 2
                        offsets = np.vstack([ (det[:,0]+det[:,2])/2-img_center[1], (det[:,1]+det[:,3])/2-img_center[0] ])
                        offset_dist_squared = np.sum(np.power(offsets,2.0),0)
                        index = np.argmax(bounding_box_size-offset_dist_squared*2.0) # some extra weight on the centering
                        det_arr.append(det[index,:])
                else:
                    det_arr.append(np.squeeze(det))
                for i, det in enumerate(det_arr):
                    det = np.squeeze(det)
                    bb = np.zeros(4, dtype=np.int32)
                    bb[0] = np.maximum(det[0]-44/2, 0)
                    bb[1] = np.maximum(det[1]-44/2, 0)
                    bb[2] = np.minimum(det[2]+44/2, img_size[1])
                    bb[3] = np.minimum(det[3]+44/2, img_size[0])
                    cropped = img[bb[1]:bb[3],bb[0]:bb[2],:]
                    scaled = misc.imresize(cropped, (160, 160), interp='bilinear')
                    scaled = prewhiten_and_expand(scaled)
                    emb = sess.run(embeddings, feed_dict={images_placeholder:scaled, phase_train_placeholder:False})
                    predictions = model.predict_proba(emb)
                    best_class_indices = np.argmax(predictions)
                    best_class_probabilities = predictions[0, best_class_indices]
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    cv2.rectangle(img, (bb[0], bb[1]), (bb[2], bb[3]), (0,255,0), 5)
                    cv2.putText(img,class_names[best_class_indices] ,(bb[0], bb[1] - 10), font, 0.5, (255,0,0),2 ,cv2.LINE_AA)
            else:
                print('No face detected')

            ret, jpeg = cv2.imencode('.jpg', img)
            frame = jpeg.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

#나중에 리액트에서 업로드한 사진 받아올 예정
@app.route('/')
def hello():
    return 'Hello, World!'

#리액트에서 업로드한 사진 받는 부분
@app.route('/upload', methods=['POST'])
def fileUpload():
    target=os.path.join(UPLOAD_FOLDER,'test')
    if not os.path.isdir(target):
        os.mkdir(target)
    logger.info("welcome to upload`")
    file = request.files['file'] 
    filename = secure_filename(file.filename)
    destination="/".join([target, filename])
    file.save(destination)
    session['uploadFilePath']=destination
    response="Whatever you wish to return"
    return response

if __name__ == '__main__':
    app.secret_key = os.urandom(24)
    app.run(host='0.0.0.0', debug=False)

flask_cors.CORS(app, expose_headers='Authorization')