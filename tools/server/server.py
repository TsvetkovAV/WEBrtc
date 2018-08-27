import argparse
import asyncio
import json
import logging
import os
import time
import wave
import pickle
import math
import cv2
import numpy
from PIL import Image
from PIL.ExifTags import TAGS
import io
import uuid
from traceback import print_exc

from lensometer import Lensometer,Dataset,Distort

import ssl
import aiohttp
from aiohttp import web

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import (AudioFrame, AudioStreamTrack, VideoFrame,
                                 VideoStreamTrack)

ROOT = os.path.dirname(__file__)
AUDIO_OUTPUT_PATH = os.path.join(ROOT, 'output.wav')
WIDTH  = 1280 # 720
HEIGHT = 720  # 1280
user_uid = 0 # for mobile as more simple

def frame_to_bgr(frame):
    data_yuv = numpy.frombuffer(frame.data, numpy.uint8) # data_flat
    data_yuv = data_flat.reshape((math.ceil(frame.height * 12 / 8), frame.width))
    return cv2.cvtColor(data_yuv, cv2.COLOR_YUV2BGR_YV12)

def frame_to_yuv(frame):
    data_flat = numpy.frombuffer(frame.data, numpy.uint8)
    return data_flat.reshape((math.ceil(frame.height * 12 / 8), frame.width))

def frame_from_bgr(data_bgr,f_width,f_height):
    #cv2.putText(data_bgr,"HELLO CLIENT! I CAN SEE YOU." , (500,70), cv2.FONT_HERSHEY_SIMPLEX, 0.89, (80,100,30), 2)
    #cv2.putText(data_bgr,"   LENSOMETER v0.0.1" , (500,100), cv2.FONT_HERSHEY_SIMPLEX, 0.89, (80,180,30), 2)
    if data_bgr.shape[0] != f_height or f_width != data_bgr.shape[1]:
        #data_bgr = data_bgr.reshape(f_height, f_width)
        # for fixing problem witj VP8 resize - keep initial size
        data_bgr = cv2.resize(data_bgr,(f_width,f_height))
    data_yuv = cv2.cvtColor(data_bgr, cv2.COLOR_BGR2YUV_YV12)
    #if data_bgr.shape[0] != f_height or f_width !=data_bgr.shape[1]:
        #data_bgr = data_bgr.reshape(f_height, f_width)
    #    data_bgr = cv2.resize(data_bgr,(f_width,f_height))
    #print('frame_from_bgr yuv',data_yuv.shape[1], data_yuv.shape[0],data_yuv.size,data_yuv.nbytes,'bgr',data_bgr.shape[1], data_bgr.shape[0])
    return VideoFrame(width=data_bgr.shape[1], height=data_bgr.shape[0], data=data_yuv.tobytes())

def get_photo_exif(data):
    photo = Image.open (data) #fromarray
    #print('verify',self.photo.verify())
    #self._photo_data_ = None
    #print('photo EXIF',type(self._photo_data_),dir(self.photo))
    model,focus,focus35,exifImageWidth,exifImageHeight = None,None,None,None,None
    if hasattr(photo,'_getexif') :
        # take FocalLength and FocalLengthIn35mmFilm
        tags = photo._getexif()
        if tags is None:
            return model,focus,focus35,exifImageWidth,exifImageHeight
        for (k,v) in tags.items():
            tag_nm = TAGS.get(k)
            #print('exif',tag_nm,v)
            if tag_nm == 'FocalLength' or tag_nm == 'FocalLengthIn35mmFilm' or tag_nm == 'Model' or tag_nm == 'ExifImageHeight' or tag_nm == 'ExifImageWidth':
                if tag_nm == 'FocalLength':
                    v = v[0]/v[1]
                    focus = v
                elif tag_nm == 'FocalLengthIn35mmFilm':
                    focus35 = v
                elif tag_nm == 'Model':
                    model = v # in case FocalLengthIn35mmFilm Undefined set default value for model
                elif tag_nm == 'ExifImageHeight':
                    exifImageHeight = int(v)
                elif tag_nm == 'ExifImageWidth':
                    exifImageWidth = int(v)
                print('exif',tag_nm,v)
                #channel.send(tag_nm + '='+str(v))
        if focus35 is None or focus35 == 0:
            # take from database
            focus35 = 29.0
    return model,focus,focus35,exifImageWidth,exifImageHeight

class Photo():
    def __init__(self, size,is_calc = False,is_dist = False):
        self._channel_status_ = 1
        self._photo_size_ = 0
        self._photo_len_  = int(size)
        self._photo_data_ = io.BytesIO()
        self._calc_by_photo_ = is_calc
        self._is_dist_     = is_dist
        self.exifImageHeight,self.exifImageWidth = None,None
        self.focus,self.focus35 = None,None
        self.model = None
        print('start get photo',self._photo_len_,is_calc)

    def is_calc(self):
        return self._calc_by_photo_
    def is_dist(self):
        return self._is_dist_


    def add_data(self,message):
        self._photo_data_.write(message)
        self._photo_size_ += len(message)

    def photo_eof(self):
        print('stop getting photo size=',self._photo_size_)
        self.model,self.focus,self.focus35,self.exifImageWidth,self.exifImageHeight = get_photo_exif(self._photo_data_)
        if self.model is not None:
            # take FocalLength and FocalLengthIn35mmFilm
            return True
        else:
            #channel.send('There is no EXIF in image.')
            print('There is no EXIF')
            return True


    def get_params(self):
        return self.model,self.focus,self.focus35,self.exifImageWidth,self.exifImageHeight

    def get_frame(self):
        #arr = numpy.asarray(bytearray(self._photo_data_)) #, dtype=numpy.uint8)
        #arr = numpy.fromstring(bytearray(self._photo_data_), dtype='int')
        img_str = self._photo_data_.getvalue() #self.photo.tobytes()
        self._photo_data_ = None
        #img_str = self.photo.tobytes()
        #with open('data.pickle', 'wb') as f:
        #    pickle.dump(img_str, f)
        arr = numpy.fromstring(img_str, numpy.uint8)
        #arr = arr.reshape((self.photo.size[1], self.photo.size[0], 4))
        #img = self.photo.convert("L")
        #arr = numpy.array(img)
        #print('arr',type(arr),arr.shape,type(self.photo),self.photo.width,self.photo.height,'mode',self.photo.mode)
        #arr = numpy.asarray(arr,dtype=numpy.uint8)
        #print('asarray',type(arr))
        frame = cv2.imdecode(arr,cv2.IMREAD_COLOR) #cv2.CV_LOAD_IMAGE_ANYDEPTH)
        #print('frame',type(frame))
        return frame

async def pause(last, ptime):
    if last:
        now = time.time()
        await asyncio.sleep(last + ptime - now)
    return time.time()


class AudioFileTrack(AudioStreamTrack):
    def __init__(self, path):
        self.last = None
        self.reader = wave.open(path, 'rb')

    async def recv(self):
        self.last = await pause(self.last, 0.02)
        return AudioFrame(
            channels=self.reader.getnchannels(),
            data=self.reader.readframes(160),
            sample_rate=self.reader.getframerate())


class VideoDummyTrack(VideoStreamTrack):
    def __init__(self,process = True,pc = None):
        width  = WIDTH
        height = HEIGHT

        self.counter = 0
        self.frame_green = VideoFrame(width=width, height=height)
        self.frame_remote = None #VideoFrame(width=width, height=height)
        self.last = None
        self.bgr_remote = None
        self.lensometer = Lensometer(algorithm=0,circle_d=98) # for old circles 146
        self.dset       = Dataset()
        self.dist       = Distort()
        self.dset_counter = 0
        self.MAX_CALIBR = 15
        self.MAX_CALC   = 20
        self.CALIBR = 'calibr'
        self.CALC   = 'calc'
        self.DSET_STOP = 'dset-stop'
        self.position_quality = False
        self.is_lens_appeared = False
        self.SPH = None
        self.width  = width
        self.height = height
        self.f_width  = width
        self.f_height = height
        self.datachannel = None
        self.transport   = 0
        self.process     = process
        self.pc          = pc
        self.track       = None
        self.is_video    = False
        print("Start session:",pc.uuid)

    def resetSize(self,width,height):
        self.width  = width
        self.height = height
        print('reset video size',width,height)

    def setSize(self,width,height):
        self.f_width  = width
        self.f_height = height
        print('setSize video size',width,height)
        self.resetSize(width,height)

    def send_channel_msg (self,msg):
        if self.datachannel is not None and self.transport == 0:
            self.datachannel.send(msg)
        else:
            print(msg)

    def dset_open(self,dtype,dname,transport=0):
        """
        Open dataset for calibration or mesure
        """
        self.transport = transport
        if dtype == self.CALIBR:
            if self.dist.open_dset(dname):
                self.dset_counter = 0
        elif dtype == self.CALC:
            if self.dset.open_dset(dname,self.width,self.height,"MJPG"):
                #set algorithm
                self.lensometer.set_algorithm(1)
                self.dset_counter = 0

    def dset_cmd(self,cmd):
        resp = {'ret' : 0}
        if cmd == self.DSET_STOP:
            resp = self.dset_eof(True,True)
        return resp

    def dset_add(self,dtype,frame):
        """
        add frame into current dataset
        """
        if frame is None:
            return {'ret': 104,'err' : 'Cant convert image'}
        resp = {'ret': 0}
        if dtype == self.CALC:
            #
            print('calc using photo')
            _,position,lens_appeared,is_dset = self.lensometer.processing_image_with_prism(frame.copy(),self.dset_counter)
            print('processing_image_with_prism',position,lens_appeared,is_dset,self.dset_counter)
            self.dset_counter += 1
            resp['cnt'] = self.dset_counter
            resp['num'] = self.dset.get_calc_num();
            resp['status'] = lens_appeared
            if self.transport == 0:
                self.image_info_to_datachannel(position,lens_appeared,is_dset,True)
            else:
                # add info about lens
                if lens_appeared:
                    SPH,CYL,AXIS,SPH1,CYL1,AXIS1 = self.lensometer.get_lens_params()
                    resp['SPH'],resp['CYL'],resp['AXIS'],resp['SPH1'],resp['CYL1'],resp['AXIS1'] = round(SPH,2),round(CYL,2),round(AXIS,2),round(SPH1,2),round(CYL1,2),round(AXIS1,2)

            if self.dset.is_open_dset():
                if lens_appeared:
                    # add only frame for which we can calculate lens params
                    self.dset.add_frame_into_dset(frame,lens_appeared)
                if self.dset.get_dset_num() > 10 or self.dset_counter > self.MAX_CALC:
                    self.dset_eof(position)
                else:
                    self.send_channel_msg('nextcalc')

        elif dtype == self.CALIBR:
            if self.dist.is_open_dset():
                print('mesure distortion',self.dset_counter)
                self.dset_counter += 1
                resp['cnt'] = self.dset_counter
                ret = self.dist.add_frame_into_dset(frame)
                resp['num'] = self.dist.get_calc_num()
                resp['status'] = ret
                if self.dist.is_dset_ready() or self.dset_counter > self.MAX_CALIBR:
                    self.dset_eof()
                else:
                    self.send_channel_msg('nextcalc')
        else:
            return {'ret': 103,'err' : 'bad cmd'}
        return resp

    def dset_add_bytes(self,dtype,bytes):
        #photo = Image.open (data)
        arr = numpy.fromstring(bytes, numpy.uint8)
        frame = cv2.imdecode(arr,cv2.IMREAD_COLOR)
        cv2.imwrite('text.png', frame)
        iob = io.BytesIO(bytes)
        model,focus,focus35,exifImageWidth,exifImageHeight = get_photo_exif(iob)
        if model is not None :
            print('photo exif',model,focus,focus35,exifImageWidth,exifImageHeight)
            if focus is not None:
                self.lensometer.set_cam_focus(focus)
                if focus35 is not None :
                    psz = self.lensometer.set_cam_psize(focus,focus35,exifImageWidth,exifImageHeight)
        else:
            print('There is no photo exif')

        return self.dset_add(dtype,frame)


    def dset_eof(self,position=False,force = False):
        """
        Close dataset for calibration or mesure
        """
        resp = {'ret': 0}
        if self.dset.is_open_dset() :
            self.dset.close_dset()
            calc_num = self.dset.get_calc_num()
            self.send_channel_msg('dataseteof num='+str(calc_num))
            ret = self.lensometer.reset_calc(True)
            resp['num'] = calc_num
            resp['status'] = ret
            self.lensometer.save_distort(self.dset.get_dset_name(),2)
            if self.transport == 0:
                self.image_info_to_datachannel(position,calc_num > 0,True)
            else:
                # send lens info
                SPH,CYL,AXIS,SPH1,CYL1,AXIS1 = self.lensometer.get_lens_avg()
                if ret:
                    resp['SPH'],resp['CYL'],resp['AXIS'],resp['SPH1'],resp['CYL1'],resp['AXIS1'] = round(SPH,2),round(CYL,2),round(AXIS,2),round(SPH1,2),round(CYL1,2),round(AXIS1,2)
                print('AVG',SPH,CYL,AXIS,SPH1,CYL1,AXIS1)

        elif self.dist.is_open_dset():
            print('dstortion EOF',self.dset_counter)
            num = self.dist.get_calc_num()
            ret = self.dist.close_dset(force)
            resp['num'] = num
            resp['status'] = ret
            if ret:
                self.lensometer.set_distort_table(self.dist)
            if self.transport == 0:
                self.datachannel.send('dataseteof num='+str(num))

        self.dset_counter = 0
        print('resp',resp)
        return resp

    def image_info_to_datachannel(self,position,lens_appeared,is_dset,force = False):
        if force or is_dset or position != self.position_quality or lens_appeared != self.is_lens_appeared or self.lensometer.SPH != self.SPH:
            self.position_quality,self.is_lens_appeared = position,lens_appeared
            self.SPH,CYL,AXIS,SPH1,CYL1,AXIS1 = self.lensometer.get_lens_params()

            if position or lens_appeared:
                if position:
                    info = ("GOOD POS " +  str(round(self.lensometer.grid_orient_std,2)))
                else:
                    info  = 'SPH,CYL,AXIS:('+str(round(self.SPH,2))+','+str(round(CYL,2))+','+str(round(AXIS,2))+')'
                    info += '--('+str(round(SPH1,2))+','+str(round(CYL1,2))+','+str(round(AXIS1,2))+')'
                    info += " Lens " + str(round(self.lensometer.lens_diff,2)) + ' ALG='+str(self.lensometer.algorithm)

                self.datachannel.send(info)
                if is_dset:
                    SPH,CYL,AXIS,SPH1,CYL1,AXIS1 = self.lensometer.get_lens_avg()
                    info  = 'AVG' if abs(SPH) > 0.25 and abs(SPH1) > 0.25 else 'NO LENS AVG'
                    info += '::SPH,CYL,AXIS:('+str(round(SPH,2))+','+str(round(CYL,2))+','+str(round(AXIS,2))+')'
                    info += '--('+str(round(SPH1,2))+','+str(round(CYL1,2))+','+str(round(AXIS1,2))+')'
                    self.datachannel.send(info)

                if lens_appeared:
                    self.datachannel.send("photo")
            else:
                self.datachannel.send("BAD POS" if not position else "LENS LOST")

    async def recv(self):
        self.last = await pause(self.last, 0.04)
        while self.bgr_remote is None: # waiting first frame from client for getting video size
            self.last = await pause(self.last, 0.04)

        self.counter += 1
        #if (self.counter == 1) :
        #    print('SEND FIRST FRAME',type(self.bgr_remote))
        if self.bgr_remote is not None:
            if self.process :
                #self.bgr_remote,position,lens_appeared = self.lensometer.processing_image(self.bgr_remote,self.counter)
                self.bgr_remote,position,lens_appeared,is_dset = self.lensometer.processing_image_with_prism(self.bgr_remote,self.counter)
                if self.datachannel is not None:
                    self.image_info_to_datachannel(position,lens_appeared,is_dset)
            #if self.counter == 1:
            #    self.datachannel.send("video")
            #print('send video',type(self.bgr_remote))
            return frame_from_bgr(self.bgr_remote,self.f_width,self.f_height)
        else:
            return self.frame_green
        #else:
        #    return self.frame_remote


async def consume_audio(track):
    """
    Drain incoming audio and write it to a file.
    """
    writer = None

    try:
        while True:
            frame = await track.recv()
            if writer is None:
                writer = wave.open(AUDIO_OUTPUT_PATH, 'wb')
                writer.setnchannels(frame.channels)
                writer.setframerate(frame.sample_rate)
                writer.setsampwidth(frame.sample_width)
            writer.writeframes(frame.data)
    finally:
        if writer is not None:
            writer.close()


async def consume_video(track, local_video):
    """
    Drain incoming video, and echo it back.
    """
    while True:
        local_video.frame_remote = await track.recv()

        #if local_video.counter < 12:
        #print('video WxH',local_video.width,local_video.height)
        data_yuv = frame_to_yuv(local_video.frame_remote)
        width,height = local_video.frame_remote.width ,local_video.frame_remote.height # frame size from client

        if local_video.bgr_remote is None: # first frame
            if not local_video.is_video and local_video.track is not None: # add video track
                #print('consume_video add track',local_video.track,width,height)
                #local_video.pc.addTrack(VideoDummyTrack(process = False,pc=local_video.pc))
                local_video.is_video = True
                local_video.setSize(width,height)
                #local_video.pc._consumers.append(asyncio.ensure_future(consume_video(local_video.track, local_video)))
        else: # check frame size
            if width != local_video.width or height != local_video.height:
                print('frame size was changed',width,height)
                # we should reset frame size and init codec
                local_video.resetSize(width,height)

        #if local_video.counter > 0:
        local_video.bgr_remote = cv2.cvtColor(data_yuv, cv2.COLOR_YUV2BGR_YV12)
        if local_video.dset.is_open_dset():
            local_video.dset.add_frame_into_dset(local_video.bgr_remote)

        #if local_video.counter < 10 :
        #    cv2.imwrite("video_"+str(local_video.counter)+'.png', local_video.bgr_remote)


async def index(request):
    #print('REQ',request.path,dir(request))
    content = open(os.path.join(ROOT, 'index.html'), 'r').read()
    return web.Response(content_type='text/html', text=content)

async def debug(request):
    #print('REQ',request.path,dir(request))
    content = open(os.path.join(ROOT, 'debug.html'), 'r').read()
    return web.Response(content_type='text/html', text=content)

async def modern(request):
    #print('REQ',request.path,dir(request))
    content = open(os.path.join(ROOT, 'modern.html'), 'r').read()
    return web.Response(content_type='text/html', text=content)


async def calibr(request):
    content = open(os.path.join(ROOT, 'calibration.html'), 'r').read()
    return web.Response(content_type='text/html', text=content)


async def javascript(request):
    print('javascript',request.path)
    content = open(os.path.join(ROOT, request.path[1:]), 'r').read()
    return web.Response(content_type='application/javascript', text=content)

#
#
#
def get_session_by_uid(uid):
    #for nm,val in pcs_uid.items():
    #    #print('pcs_uid',nm,val[0].uuid)
    #    if uid == nm:
    #        return val[0]
    return pcs_uid[uid][0] if uid in pcs_uid else None

#
# websock mode
#
async def websocket_handler(request):
    print('Websocket connection starting',request)
    ws = web.WebSocketResponse()
    print('Websocket WebSocketResponse',ws)
    await ws.prepare(request)
    print('Websocket connection ready')

    async for msg in ws:
        print(msg)
        if msg.type == aiohttp.WSMsgType.TEXT:
            print(msg.data)
            if msg.data == 'close':
                await ws.close()
            else:
                await ws.send_str(msg.data + '/answer')

    print('Websocket connection closed')
    return ws

#
# for post mode
#
async def mesure_handler(request):
    print('mesure_handler',type(request.content),request.query,'method')
    data = await request.post()
    if 'uid' not in request.query or 'cmd' not in request.query:
        return web.json_response({'ret': 100,'err' : 'bad args'}) #web.Response(status=200,text='ARGS ERROR')
    uid = request.query['uid']
    cmd = request.query['cmd']
    dsetnm = request.query['dsetnm'] if 'dsetnm' in request.query else ''
    print('UID',uid,'dset',dsetnm)
    pc = get_session_by_uid(uid)

    if pc is not None and pc.lvideo is not None and 'blob' in data:
        print('session',pc,pc.lvideo)
        blob = data['blob'].file
        content = blob.read()
        print('mesure_handler::content',type(content))
        pc.lvideo.dset_open(cmd,dsetnm,2)
        resp = pc.lvideo.dset_add_bytes(cmd,content)
    else:
        resp = {'ret': 102,'err' : 'bad session'}
    return web.json_response(resp) #web.Response(status=200,text='OK')

#
# get result
async def result_handler(request):
    print('result_handler',type(request.content),request.query,'method')
    if 'uid' not in request.query or 'cmd' not in request.query:
        return web.json_response({'status':False,'ret': 100,'err' : 'bad args'})
    uid = request.query['uid']
    cmd = request.query['cmd']
    pc = get_session_by_uid(uid)
    if pc is None or pc.lvideo is None:
        return web.json_response({'status':False,'ret': 101,'err' : 'bad uid'})
    #
    resp = pc.lvideo.dset_cmd(cmd)
    return web.json_response(resp)



async def offer(request):
    global user_uid # for session synchronization
    offer = await request.json()
    #print('OFFER',offer)
    offer = RTCSessionDescription(
        sdp=offer['sdp'],
        type=offer['type'])

    pc = RTCPeerConnection()
    pc._consumers = []
    user_uid += 1
    #pc.uuid = str(uuid.uuid1())
    pc.uuid = str(user_uid)
    pcs.append(pc)
    #print('RTCPeerConnection',dir(RTCPeerConnection))
    # prepare local media
    local_audio = AudioFileTrack(path=os.path.join(ROOT, 'demo-instruct.wav'))
    local_video = VideoDummyTrack(process = False,pc=pc)
    pc.lvideo = local_video

    #local_video.process = False
    #local_video.pc = pc
    @pc.on('datachannel')
    def on_datachannel(channel):
        #print("on_datachannel",channel)

        local_video.datachannel = channel
        channel._channel_status_ = 0
        channel.counter = 0
        @channel.on('message')
        def on_message(message):
            global user_uid # for session synchronization
            #
            # start getting photo
            # here we can use message from client browser
            if channel._channel_status_ == 0:
                print('msg',message)
                if message == 'process':
                    local_video.process = not local_video.process # switch video process mode
                elif message == 'algorithm':

                    local_video.lensometer.set_algorithm()
                elif message[0:7] == 'chequer'  :
                    # distortion
                    print('chequer')
                    local_video.dset_open(local_video.CALIBR,message[8:])
                elif message[0:9] == 'dset-stop'  :
                    #print('STOP DSET')
                    local_video.dset.ask_close_dset()
                    #print('STOP DSET DONE',local_video.dset.is_open_dset())
                elif message[0:10] == 'dsetcancel':
                    local_video.dset_eof(force=True)
                elif message[0:4] == 'dset'    :
                    #print('SAVE DSET ',message[5:])
                    local_video.dset_open(local_video.CALC,message[8:])
                    #print('SAVE DSET ',message[5:],local_video.dset.is_open_dset())
                elif message[0:7] == 'pixsize'    : # from calibr.js
                    # monitor pixel size
                    if pc.uuid is None:
                        user_uid += 1
                        #pc.uuid = str(uuid.uuid1())
                        pc.uuid = str(user_uid)
                    monpix = float(message[8:])
                    pcs_uid[pc.uuid] = (pc,monpix) # set or update
                    if local_video.lensometer is not None :
                        #set for destop session
                        local_video.lensometer.set_mon_pix(monpix)
                    channel.send('userId '+ pc.uuid)
                elif message[0:6] == 'userId'    :
                    # monitor pixel size
                    uid = message[7:]
                    try:
                        _,pixsize = pcs_uid[uid]
                        channel.send('pixsize='+str(pixsize))
                        print('user ID',uid,'pixsize',pixsize)
                        if local_video.lensometer is not None :
                            local_video.lensometer.set_mon_pix(pixsize)

                    except KeyError:
                        channel.send('session expired '+ uid)
                        print('user session expired',uid)
                elif message[0:5] == 'photo':
                    channel._channel_status_ = 1
                    channel._photo_ = Photo(message[6:])

                elif message[0:4] == local_video.CALC:
                    channel._photo_ = Photo(message[5:],is_calc = True)
                    channel._channel_status_ = 1
                elif message[0:4] == local_video.CALIBR:
                    channel._photo_ = Photo(message[5:],is_dist = True)
                    channel._channel_status_ = 1

                elif message == 'Ping' :
                    channel.send('pong frame '+str(local_video.counter))
            else: # photo mode
                if message[0:8] == 'photoeof':
                    #print('stop send photo size=',channel._photo_size_)
                    channel._channel_status_ = 0
                    if channel._photo_.photo_eof() :
                        # there is exif
                        if local_video.lensometer is not None :
                            # set focus and  pixel size
                            _,focus,focus35,exifImageWidth,exifImageHeight = channel._photo_.get_params()
                            if focus is not None:
                                local_video.lensometer.set_cam_focus(focus)
                            if focus35 is not None and focus is not None:
                                psz = local_video.lensometer.set_cam_psize(focus,focus35,exifImageWidth,exifImageHeight)
                                channel.send('Cam pixel size='+str(psz))
                            if channel._photo_.is_calc():
                                frame = channel._photo_.get_frame()
                                local_video.dset_add(local_video.CALC,frame)

                            elif channel._photo_.is_dist():
                                frame = channel._photo_.get_frame()
                                local_video.dset_add(local_video.CALIBR,frame)

                    # drop photo
                    channel._photo_ = None

                else:
                    # photo data
                    channel._photo_.add_data(message)


    @pc.on('track')
    def on_track(track):
        if track.kind == 'audio':
            pc.addTrack(local_audio)
            pc._consumers.append(asyncio.ensure_future(consume_audio(track)))
        elif track.kind == 'video':
            #print('ADD VIDEO TRACK')
            local_video.track = track
            pc.addTrack(local_video)
            pc._consumers.append(asyncio.ensure_future(consume_video(track, local_video)))

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type='application/json',
        text=json.dumps({
            'sdp': pc.localDescription.sdp,
            'type': pc.localDescription.type
        }))


pcs = [] # RTCPeerConnection list
pcs_uid = {}

async def on_shutdown(app):
    # stop audio / video consumers
    print('on_shutdown connections:',len(pcs))
    for pc in pcs:
        print('connection consumers:',len(pc._consumers))
        for c in pc._consumers:
            c.cancel()

    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='WebRTC audio / video / data-channels demo')
    parser.add_argument('--port', type=int, default=8080,
                        help='Port for HTTP server (default: 8080)')
    parser.add_argument('--verbose', '-v', action='count')
    parser.add_argument('-s', '--ssl', action='count')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    app = web.Application()
    print('app',app)
    if args.ssl:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH ) #CLIENT_AUTH SERVER_AUTH
        ssl_cert = 'server.crt'
        ssl_key =  'server.key'
        context.load_cert_chain(str(ssl_cert), str(ssl_key))
        #context.verify_mode = ssl.CERT_NONE
        #context = ssl.create_default_context()
        #context.check_hostname = False
        context.verify_mode = ssl.CERT_OPTIONAL # CERT_OPTIONAL
    else:
        context = None


    #app = web.clone(scheme='https').Application() # my code
    app.on_shutdown.append(on_shutdown)
    app.router.add_get('/', index)
    app.router.add_get('/debug', debug)
    app.router.add_get('/modern', modern)
    app.router.add_get('/js/capture.js', javascript)
    app.router.add_get(r'/*.js', javascript)
    #app.router.add_get(r'/js/*.js', javascript)
    app.router.add_get('/calibr', calibr)
    app.router.add_post('/offer', offer)
    app.router.add_static('/img/', path=str('./img/') )
    app.router.add_static('/css/', path=str('./css/') )
    app.router.add_static('/static/', path=str('./static/') )
    #app.router.add_static('/', path=str('./') )
    app.router.add_get('/client.js', javascript)
    app.router.add_get('/calibr.js', javascript)
    app.router.add_get('/dclient.js', javascript)
    app.router.add_route('GET', '/ws', websocket_handler)
    app.router.add_route('GET', '/wss', websocket_handler)
    app.router.add_route('POST', '/mesure', mesure_handler)
    app.router.add_route('GET', '/result', result_handler)

    web.run_app(app, port=args.port,ssl_context=context)
