#
# lensometer
#
import numpy as np
import cv2
import math
import array
import datetime
import glob
import sys
import argparse
import numpy
import copy
import os
import pickle
from traceback import print_exc

def_conf = {
'blur_val' : 5,
'canny_lower' : 50,'canny_upper' : 100,
'min_elem_for_ellipse':5,
'solidity_circle' : 0.9,
'center_offset' : 2,
'min_inserted' : 3,
'min_MA': 20,
'min_MA_diff' : 1.1,
'min_LENS_diff': 10,
'font_scale':0.4,
'font_scale_orient':0.6,
}

lenses_type = {
'+1' : (1,0,0),
'+2' : (2,0,0),
'-2' : (-2,0,0),
'-3' : (-3,0,0),
'+0,5+1,75' : (0.5,1.75,0),
'+0,25-0,25' : (0.25,-0.25,0),
'+2,5+1,75' : (2.5,1.75,0),
'+2-2' : (2.0,-2.0,0),
'-3,75-2,25' : (-3.75,-2.25,0),
'-3-0,75' : (-3.0,-0.75,0),
'-1-1,75' : (-1.0,-1.75,0),
'-4-0,5' : (-4.0,-0.5,0)
}

class Lensometer():
    def __init__(self,conf = def_conf,min_MA=None,min_MA_diff=None,center_offset=None,algorithm=0,F2=0.039,D=0.22,L=0.10,monpix=0.0002726,campix=0.000044, circle_d=146):
        if conf is not None:
            self.blur_val    = conf['blur_val']
            self.canny_lower = conf['canny_lower']
            self.canny_upper = conf['canny_upper']
            self.find_cont_retr_mode = cv2.RETR_TREE
            self.min_elem_for_ellipse = conf['min_elem_for_ellipse']                                 # min elements into contour for being ellipse
            self.solidity_circle = conf['solidity_circle']                                           # threshold for contour solidity
            self.center_offset   = conf['center_offset'] if center_offset is None else center_offset # offset between circles center in group
            self.min_inserted    = conf['min_inserted']                                              # threshold for circle's embedded level
            self.min_MA          = conf['min_MA'] if min_MA is None else min_MA                      # threshold for circle's size which we will take into account
            self.min_MA_diff     = conf['min_MA_diff'] if min_MA_diff is None else min_MA_diff       # spatial threshold 0.6 for 0.25, 1.0 for more then 0.25
            self.min_LENS_diff   = conf['min_LENS_diff']                                             # spatial threshold
            self.show_grid_for_scan_mode = True
            self.show_frame_num          = not True
            self.use_mask                =  False          # use mask for target image
            self.show_remote             =  not True       # show remote frame into our frame
            # circles Info
            self.show_angl,self.show_num,self.show_elp = True,True,True # switch on/off circles info
            self.font_scale        = conf['font_scale']
            self.font_scale_orient = conf['font_scale_orient'] # font size
            self.debug = False
            self.s_w,self.s_h = 320,240
            self.red_color = (255,0,0)
            self.blue_color = (0,0,255)
            self.green_color = (0,240,0)
            self.black_color = (0,0,0)
            # cameras and monitor info
            self.OBJ_H      = circle_d #size our circles into pixels
            self.cam_pix_sz = campix  # m 0.000004
            self.mon_pix_sz = monpix
            self.H  = self.mon_pix_sz * self.OBJ_H  # 0.0264
            self.algorithm = algorithm  # use distance
            # for D calculating
            self.use_2lens  = True # calc for 2 lens
            self.F2 = F2     # cam focus
            self.L  = L      # cam->lens distance
            self.D01 = D - L # obj->lens distance
            self.d35 = 0.04327 # m
            print('config','MPIX',self.mon_pix_sz,'H',self.H,conf)


        self.contours   = []
        self.hierarchy  = []
        self.cont_types = []
        self.ctype      = []
        self.cont_ellipses = []
        self.circles_grid  = []
        self.MIN_GRID_X,self.MIN_GRID_Y = None,None
        self.circles_group = []
        self.lens_group = []
        self.base_group = []
        self.circles8_group = [] # circles relating to lenses,rest circles from grid,all group with 8 circles
        self.grid_point_num = 0
        self.grid_orient_std = 0
        self.lens_std        = 0
        self.lens_diff       = 0
        self.position_quality = False   # status of spatial
        self.is_lens_appeared = False
        self.file_scan_mode   = True
        self.lens_type        = 'xxx'
        self.max_calc         = 20
        self.num_calc         = 0 # number calculation with out being interrupted
        self.SPH_LIST,self.CYL_LIST,self.AXIS_LIST = [],[],[]
        self.SPH1_LIST,self.CYL1_LIST,self.AXIS1_LIST = [],[],[]
        self.SPH,self.CYL,self.AXIS,self.SPH1,self.CYL1,self.AXIS1 = 0,0,0,0,0,0
        self.AV_SPH,self.AV_CYL,self.AV_AXIS,self.AV_SPH1,self.AV_CYL1,self.AV_AXIS1 = 0,0,0,0,0,0
        self.dist = None

    def set_mon_pix(self,monpix):
        self.mon_pix_sz = monpix/1000
        self.H  = self.mon_pix_sz * self.OBJ_H
        print('set_mon_pix',self.H)

    def set_cam_focus(self,F): # in mm
        self.F2 = F*0.001
        print('set_cam_focus',self.F2)

    def set_cam_psize(self,focus,focus35,X,Y):
        d = (focus*self.d35)/focus35
        self.cam_pix_sz = d/math.sqrt(X**2+Y**2)
        print('set_cam_psize',self.cam_pix_sz)
        return self.cam_pix_sz

    def set_distort_table(self,dist =None):
        self.dist = dist

    def set_algorithm(self,nval = None):
        if nval is not None:
            self.algorithm = nval
            return
        self.algorithm = 1 if self.algorithm == 0 else 0
        print('algorithm',self.algorithm)

    def point_distance(self,dx,dy):
        if  dx < 0 :
           dx = -dx
        if  dy < 0 :
           dy = -dy
        x,y = math.ceil(dx),math.ceil(dy)
        return (123*y+51*x)/128 if dx < dy else  (123*x+51*y)/128

    def get_fit_ellipse(self,n):

         ellipse = self.cont_ellipses[n]
         if type(ellipse) is bool :
             ellipse = cv2.fitEllipse(self.contours[n])
             self.cont_ellipses[n] = ellipse
         return ellipse

    def is_our_contour(self,c):
    	# approximate the contour

        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
    	# the contour is 'bad' if it is not a rectangle
        if len(approx) <= 4:
            return False
        area = cv2.contourArea(c)
        hull = cv2.convexHull(c)
        hull_area = cv2.contourArea(hull)
        solidity = float(area)/hull_area
        return True if hull_area > 0 and solidity > self.solidity_circle and len(c) > self.min_elem_for_ellipse else False # len(c) > 5 for elipse

    #
    # get number of embedded circles with nearest centre XY for contour 'n'
    #
    def get_circle_num(self,h,n):
        #global circles_group,grid_point_num,cont_ellipses

        num = self.circles_group[n]
        if num != -1 :
            #print('ret circle num',n,num)
            return num
        # calculate embedded level for circle[n]
        group = [] # for list embedded circles
        num,parent = 1, h[3]
        group.append(n)

        while parent != -1:
            if self.cont_types[parent] :
                group.insert(0,parent)
            parent = self.hierarchy[parent][3]
        child = h[2]
        while child != -1:
            if self.cont_types[child] :
                group.append(child)
            child = self.hierarchy[child][2]
        # Ordered list
        tgroup = []  # embedded circle sorted from external to internal
        num,j  = 1,0
        #print('CALC GROUP',n,len(group),group)
        for i in group:
            if j > 0:
                (px,py),(PMA,Pma),_ = self.get_fit_ellipse(i)
                distance = self.point_distance(x-px,y-py)
                if distance < self.center_offset and PMA > self.min_MA : # belong to group
                    num += 1
                    tgroup.append(i)
                    #print('XY',j,i,(x,y),(px,py),distance,MA-PMA,'num',num)
                    (x,y),(MA,ma) = (px,py),(PMA,Pma)
                else:
                    #print('ignore',i,j,'dist',distance,PMA,'>',self.min_MA)
                    self.circles_group.insert(i,1)
            else:
                tgroup.append(i)
                (x,y),(MA,ma),_ = self.get_fit_ellipse(i)
            j += 1
        #print('TGROUP',num,'>', min_inserted,'num',grid_point_num)
        if num > self.min_inserted: # new group of circles belonging to our grid point because of number embedded circles
            self.circles_grid.append(tgroup)
            (x,y),_,_ = self.get_fit_ellipse(tgroup[0])
            if x < self.MIN_GRID_X:
                self.MIN_GRID_X = x
            if y < self.MIN_GRID_Y:
                self.MIN_GRID_Y = y
            self.grid_point_num += 1
            #print('CALC TGROUP',n,num,grid_point_num,tgroup)
        for i in tgroup:
            self.circles_group[i] = num
        #print('CALC TGROUP',n,num,tgroup)

        return num

    #
    # get inserted contours num
    #
    def get_ins_cont_num(self,elem):

        ct,h,n = elem[0],elem[1],elem[2]
        #print('add_contour_num:cont_types',len(cont_ellipses))
        return (True,self.get_circle_num(h,n)) if ct else (False,0)


    def select_circles_grid(self,frame,counter):
        height, width = frame.shape[:2]
        cell_Y = self.OBJ_H*2.5    # 2
        cell_X = self.OBJ_H/20   # 20
        self.MIN_GRID_Y,self.MIN_GRID_X = height, width
        width = math.floor(width/cell_X)+1
        height = math.floor(height/cell_Y)+1

        print('cellXY',(cell_X,cell_Y),(width,height))
        def pos_in_grid(val):
            (x,y),_,_ = self.get_fit_ellipse(val[0])
            num = len(val)
            yb = math.floor((y-self.MIN_GRID_Y)/cell_Y)
            xx,yy = math.floor((x-self.MIN_GRID_X)/cell_X),(yb + (0 if num < 6 else height)) # height
            v = xx+(yy*width)
            print('pos_in_grid',(x,y),(xx,yb,yy),v)
            return v
        print('select circle',counter)
        #global contours,hierarchy,cont_types,ctypes,circles_grid,circles_group,grid_point_num,cont_ellipses
        img = cv2.medianBlur(frame,self.blur_val)
        cimg = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY )

        edged = cv2.Canny(cimg, self.canny_lower,self.canny_upper)
        _, self.contours, hierarchy = cv2.findContours( edged.copy(), self.find_cont_retr_mode , cv2.CHAIN_APPROX_SIMPLE)

        if self.contours is not None and hierarchy is not None:


            if self.debug :
                print('contours',len(self.contours))
            #cv2.drawContours( img, self.contours, -1, (0,0,255), 2, cv2.LINE_AA, hierarchy, 1 )
            self.circles8_group = []
            self.circles_grid = []
            self.circles_group = [-1 for x in range(len(self.contours))]
            self.cont_ellipses = [False for x in range(len(self.contours))]
            self.grid_point_num = 0
            self.hierarchy = hierarchy[0]
            contour_index = range(len(self.contours))
            self.cont_types = [self.is_our_contour(x) for x in self.contours]
            print('cont_types',len(self.cont_types),len(selfself.contours))
            self.ctypes     = [self.get_ins_cont_num(x) for x in zip(self.cont_types,self.hierarchy,contour_index)]

            # sort self.circles_grid
            print('MIN Y X ',self.MIN_GRID_Y,self.MIN_GRID_X)
            self.circles_grid.sort(key=pos_in_grid)
            print('circles_grid',self.circles_grid)


        return img
    #
    # understand where are lens
    # lens_group is  bottom or left row of lenses
    def set_lens_group(self,lens_group,base_group):
        (x,y),(MA,ma),AXIS = self.get_fit_ellipse(lens_group[0])
        (x0,y0),(MA0,ma0),AXIS0 = self.get_fit_ellipse(lens_group[1])
        (x1,y1),(MA1,ma1),AXIS1 = self.get_fit_ellipse(base_group[0])
        (x10,y10),(MA10,ma10),AXIS10 = self.get_fit_ellipse(base_group[1])
        lens_pos_type = (y > (y1+MA) and y0 > (y10+MA)) or ((x+MA) < x1 and (x0+MA) < x10)
        self.lens_group = lens_group if lens_pos_type else base_group
        self.base_group = base_group if lens_pos_type else lens_group

    #
    # check lenses by look for diff between circles(8)
    #
    def check_lens_presence(self,flow = False):

        if not flow:
            self.position_quality,self.is_lens_appeared = False,False
        grid_MA = []
        self.lens_group,self.base_group = [],[]
        self.base_elipse = []
        lens_group,base_group = [],[]
        #print('check_lens_presence','pos',position_quality,'lens',is_lens_appeared)
        # circles_grid at this point sorted by position
        for val in self.circles_grid:   # .values() .itervalues()
            if len(val) > 4: # number embedded circles
                i = val[0] # take first external circle
                _,(MA,ma),_ = self.get_fit_ellipse(i)
                grid_MA.append(MA)
                base_group.append(i)
                #print('circles8',MA,val)
        #

        # circles group for calculation
        self.circles8_group = base_group

        if len(grid_MA) > 2: # min circles for calculate
            ma_max,ma_min,mean,self.grid_orient_std,var = max(grid_MA),min(grid_MA),np.mean(grid_MA),np.std(grid_MA),np.var(grid_MA)
            diff = ma_max-ma_min
            #print('grid_MA',len(grid_MA),grid_MA,'base',base_group)
            if diff < self.min_MA_diff :
                if not self.position_quality:
                    self.position_quality,self.is_lens_appeared = True,False
                    if self.debug :
                        print('enter into CORRECTLY ORIENT state',diff,self.grid_orient_std,mean,var)
            else: # bad position or lens appeared
                grid_lens,num,i = [],0,0

                #print('check lens ',diff,std,mean,var)
                for ma in grid_MA:
                    #print('lens',abs(ma-ma_min),std)
                    if abs(ma-ma_min) > self.min_MA_diff:
                        grid_lens.append(ma)
                        lens_group.append(base_group[i])
                        #print('add lens')
                    i += 1
                num = len(grid_lens)
                base_group = list(set(base_group) - set(lens_group))
                # check where realy were lens

                #print('grid_lens',is_lens_appeared,num,grid_lens,base_group)
                if num > 1 :
                    lens_max,lens_min,self.lens_std = max(grid_lens),min(grid_lens),np.std(grid_lens)
                    self.lens_diff = lens_max - lens_min
                    #print('lens',lens_diff,lens_std)
                    if self.use_2lens or self.lens_diff < self.min_LENS_diff: # or self.use_2lens because lens params could be difference

                        if not self.is_lens_appeared : # and (position_quality or file_scan_mode):
                            print('LENSES appeared ',num,self.lens_diff,self.lens_std)
                            self.is_lens_appeared = True
                            if len(base_group) > 1:
                                self.set_lens_group(lens_group, base_group)
                            return num # calculate lens params
                    else:
                        self.is_lens_appeared = False

                self.position_quality = False
                if not self.is_lens_appeared:
                    pass
                    if self.debug :
                        print('leaved GOOD position ',diff,self.grid_orient_std,mean,var)
        # there are no lens group
        return 0
    #
    # check lenses by look for points for prism
    #
    def check_lens_presence2(self,flow = False):
        base_group = []
        self.is_lens_appeared = False
        for val in self.circles_grid:
            if len(val) > 4: # number embedded circles
                i = val[0] # take first external circle
                base_group.append(i)
        self.circles8_group = base_group
        if len(base_group) < 4:
            return 0

        self.base_group = []
        self.lens_group = [base_group[2],base_group[3]]
        self.is_lens_appeared = True
        return 2

    def set_base_circles(self):
        base_group = []
        for val in self.circles_grid:
            if len(val) > 4: # number embedded circles
                i = val[0] # take first external circle
                base_group.append(i)
        self.base_elipse = [self.get_fit_ellipse(base_group[0]),self.get_fit_ellipse(base_group[1])] if len(base_group) == 4 else []


    #
    # draw cross and circles params
    #
    def draw_cross(self,surf,i,c,h,num,ellipse):
        #global cont_types
        #solidity = float(area)/hull_area
        (x,y),(MA,ma),angle = ellipse
        #print('cross','MA',MA,ma,angle )
        leftmost  = c[c[:,:,0].argmin()][0][0]
        rightmost = c[c[:,:,0].argmax()][0][0]
        #print('l,r',leftmost,rightmost)
        cv2.line(surf,(int(leftmost),int(y)),(int(rightmost),int(y)),self.red_color,1)
        topmost  = c[c[:,:,1].argmin()][0][1]
        bottmost = c[c[:,:,1].argmax()][0][1]
        cv2.line(surf,(int(x),int(topmost)),(int(x),int(bottmost)),self.red_color,1)

        if h[3] < 0 or not self.cont_types[h[3]] : # no parent or parent rect ,h[2] < 0 child contour
            circle_info = ''
            if i != -1 :
                circle_info += str(i)
            circle_info += ' ' + str(round(MA,1))
            circle_info += ((' ' + str(round(angle,1))) if self.show_angl else '')
            circle_info += ((' ' + str(round(MA/ma,2))) if self.show_elp else '')
            circle_info += ((' ' + str(num)) if self.show_num else '')
            #print(circle_info)
            cv2.putText(surf, circle_info , (int(rightmost+2),int(y)), cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, self.red_color, 1)




    #
    # draw grid circles and circle's params and status of spatial orientation and lense's info if that were checked
    #
    def draw_grid(self,frame,draw_lens = False):
        # draw node of our grid
        def draw_grid_point(n,i,color,verb = False):
            try:
                (x,y),(MA,ma),angle = self.get_fit_ellipse(n)
                c,h,desc = self.contours[n],self.hierarchy[n],self.ctypes[n]
            except :
                print_exc()
                return
            if desc[0] and desc[1] > self.min_inserted: # is our circle
                if verb:
                    print('draw_grid_point')
                cv2.drawContours(surf, [c], -1, color if desc[1] > 4 else self.blue_color, 1, cv2.LINE_AA) # thickness -1
                self.draw_cross(surf,i, c, h,desc[1],((x,y),(MA,ma),angle))


        def draw_lens_point(n,color):
            try:
                (x,y),(MA,ma),angle = self.get_fit_ellipse(n)
                c,h,desc = self.contours[n],self.hierarchy[n],self.ctypes[n]
            except :
                print_exc()
                return
            if desc[0] and desc[1] > self.min_inserted: # is our circle
                cv2.drawContours(surf, [c], -1, color if desc[1] > 4 else self.blue_color, 1, cv2.LINE_AA) # thickness -1
                #self.draw_cross(surf,i, c, h,desc[1],((x,y),(MA,ma),angle))


        im_scale = None
        if self.show_remote:
            im_scale = cv2.resize(frame, (self.s_w,self.s_h), interpolation = cv2.INTER_AREA)
            cv2.rectangle(im_scale, (0,0), (self.s_w,self.s_h), self.red_color, thickness=2)

        mask = np.ones(frame.shape[:2], dtype="uint8") * 255 if self.use_mask else None
        surf = mask if self.use_mask else frame
        circle_color =  self.black_color if self.use_mask else self.red_color
        #print('DRAW GRID',len(self.circles_grid),len(self.cont_types),self.grid_point_num,self.circles_grid,self.circles8_group)
        I = 0
        for val in self.circles_grid: # .values() itervalues() 2.6v
            for n in val: # point of grid
                draw_grid_point(n,I,circle_color)
            I += 1
        # show lens
        if draw_lens:
            for n in self.lens_group:
                print('show lens',n)
                draw_lens_point(n,self.green_color)

        # draw status grid
        if len(self.circles8_group) > 3 and (self.position_quality or self.is_lens_appeared):
            try:
                (x,y),(MA,ma),_ = self.get_fit_ellipse(self.circles8_group[0])
                (x1,y1),_,_ = self.get_fit_ellipse(self.circles8_group[3])
            except :
                print('circles8_group',self.circles8_group[0],self.circles8_group[3],'num',len(self.cont_ellipses),'cont',len(self.contours))
                print_exc()
                return surf
            px = int((x if x < x1 else x1) + MA)
            py = int((y if y < y1 else y1) + MA)
            if self.position_quality:
                info = "Good spatial orientation " + str(round(self.grid_orient_std,2))
                cv2.putText(surf,info , (px,py), cv2.FONT_HERSHEY_SIMPLEX, self.font_scale_orient, (80,100,30), 1)
            else:
                if True:
                    info  = 'SPH,CYL,AXIS:('+str(round(self.SPH,2))+','+str(round(self.CYL,2))+','+str(round(self.AXIS,2))+')'
                    info += '--('+str(round(self.SPH1,2))+','+str(round(self.CYL1,2))+','+str(round(self.AXIS1,2))+')'
                    info += " Lens " + str(round(self.lens_diff,2))
                    info += " [" + str(self.num_calc) + "]"
                    cv2.putText(surf,info , (px,py), cv2.FONT_HERSHEY_SIMPLEX, self.font_scale_orient, (80,100,30), 1)
                    if self.AV_SPH != 0:
                        info  = 'AVG::SPH,CYL,AXIS:('+str(round(self.AV_SPH,2))+','+str(round(self.AV_CYL,2))+','+str(round(self.AV_AXIS,2))+')'
                        info += '--('+str(round(self.AV_SPH1,2))+','+str(round(self.AV_CYL1,2))+','+str(round(self.AV_AXIS1,2))+')'
                        cv2.putText(surf,info , (px,py+20), cv2.FONT_HERSHEY_SIMPLEX, self.font_scale_orient, (80,100,30), 1)

        if self.show_remote:
            # add source video
            y_off,x_off = surf.shape[0]-self.s_h-1,surf.shape[1]-self.s_w-1
            surf[y_off:y_off+im_scale.shape[0], x_off:x_off+im_scale.shape[1]] = im_scale
            #surf.paste(scale, (0,0))
        # remove the contours from the image and show the resulting images
        if self.use_mask :
            cv2.bitwise_and(frame, frame, mask=mask)
        #cv2.imshow('Mask',surf)
        return surf
    #
    # calculate lens params
    #
    def calc_lens(self,lens_type = 'xxx'):
        def calc_D(m0):
            dj1 = m0 * self.D01*(self.L - self.F2)/(self.F2-self.L-self.D01+m0*self.D01)
            return 1/dj1 + 1/self.D01

        def calc_S(h1,h2):
            ltype = h1>h2
            h1 = -(h1*self.cam_pix_sz)
            h = -self.H
            h2 *= self.cam_pix_sz
            F = h * self.F2 / (4*h1*h1*(1/h1 + 1/h2))
            D = 1/F
            #if ltype and D > 0:
            #   D = -D
            return D
        def get_coord(n):
            (x,y),_,_ = self.get_fit_ellipse(n)
            return (round(x,1),round(y,1))
        # check lens_group group on containing only circles from bottom or left or maybe change method of selecting
        #print('  calculate lens params','2lens',self.use_2lens,'lenses',map(get_coord,self.lens_group),'base',map(get_coord,self.base_group))
        try:
            # just take values from table
            lens_val = lenses_type[lens_type]
            print('     SPH',lens_val[0],'CYL',lens_val[1], 'AXIS',lens_val[2])
            self.SPH  = float(lens_val[0])
            self.CYL  = float(lens_val[1])
            self.AXIS = float(lens_val[2])
            return True

        except KeyError:
            #print('calc_lens',self.lens_group,'base',self.base_group)
            # in case of using bottom or left circles for lens
            if self.use_2lens and not (len(self.lens_group) == 2 and ((len(self.base_group) == 2) or (len(self.base_elipse) == 2))):
                self.is_lens_appeared = False
                return False# skip

            (x,y),(MA,ma),AXIS = self.get_fit_ellipse(self.lens_group[0])
            (x0,y0),(MA0,ma0),AXIS0 = self.get_fit_ellipse(self.lens_group[1])
            (x1,y1),(MA1,ma1),AXIS1 = self.base_elipse[0] if len(self.base_elipse) == 2 else self.get_fit_ellipse(self.base_group[0])
            (x10,y10),(MA10,ma10),AXIS10 = self.base_elipse[1] if len(self.base_elipse) == 2 else self.get_fit_ellipse(self.base_group[1])
            lens_pos_type = (y > (y1+MA) and y0 > (y10+MA)) or ((x+MA) < x1 and (x0+MA) < x10)#  lens_group is  bottom or left row of lenses

            def algorithm0(MA,MA1,ma,ma1,AXIS,AXIS1):
                m0 = MA/MA1 if lens_pos_type else MA1/MA
                m1 = MA/ma
                axis = AXIS if lens_pos_type else AXIS1
                SPH = calc_D(m0)
                CYL = calc_D(m1)
                print('calc',(x,y),(x1,y1), 'M0', m0, 'm1', m1, 'SPH', SPH, "CYL", CYL, 'AXIS',axis)
                return SPH,CYL,axis

            def algorithm1(MA,MA1,ma,ma1,AXIS,AXIS1):
                # use size of object
                if lens_pos_type:
                    h1,h2 = MA1,MA  # base, lens
                    a1,a2,axis = MA,ma,AXIS
                else:
                    h1,h2 = MA,MA1  # base, lens
                    a1,a2,axis = MA1,ma1,AXIS1
                SPH = calc_S(h1,h2)
                CYL = calc_S(a1,a2)
                #print('calc',(round(x,1),round(y,1)),(round(x1,1),round(y1,1)),'LP',lens_pos_type,'H',round(self.H,4),'H1',round(h1,2),'H2',round(h2,2),'SPH', SPH, "CYL", CYL, 'AXIS', axis)
                return SPH,CYL,axis

            algorithm = algorithm0 if self.algorithm == 0 else algorithm1
            self.SPH,self.CYL,self.AXIS    = algorithm(MA, MA1, ma, ma1,AXIS,AXIS1)
            self.SPH1,self.CYL1,self.AXIS1 = algorithm(MA0,MA10,ma0,ma10,AXIS0,AXIS10)
            self.SPH_LIST.append(self.SPH)
            self.SPH1_LIST.append(self.SPH1)
            self.CYL_LIST.append(self.CYL)
            self.CYL1_LIST.append(self.CYL1)
            self.AXIS_LIST.append(self.AXIS)
            self.AXIS1_LIST.append(self.AXIS1)

            self.num_calc += 1
            return True
    #
    #
    def reset_calc(self,force = False):
        ret = False
        if force or self.num_calc > self.max_calc: # there is dataset
            if self.num_calc > 0:
                self.AV_SPH,self.AV_CYL,self.AV_AXIS = np.median(self.SPH_LIST),np.median(self.CYL_LIST),np.median(self.AXIS_LIST) # mean
                self.AV_SPH1,self.AV_CYL1,self.AV_AXIS1 = np.median(self.SPH1_LIST),np.median(self.CYL1_LIST),np.median(self.AXIS1_LIST)
                ret = True
            self.SPH_LIST,self.CYL_LIST,self.AXIS_LIST = [],[],[]
            self.SPH1_LIST,self.CYL1_LIST,self.AXIS1_LIST = [],[],[]


        self.num_calc = 0
        return ret
    def set_max_calc(self,nval):
        self.max_calc = nval
    def is_calc_interrupted(self,old):
        return old == self.num_calc or self.num_calc > self.max_calc

    def get_lens_params(self):
        return self.SPH,self.CYL,self.AXIS,self.SPH1,self.CYL1,self.AXIS1

    def get_lens_avg(self):
        return self.AV_SPH,self.AV_CYL,self.AV_AXIS,self.AV_SPH1,self.AV_CYL1,self.AV_AXIS1

    def get_num_calc(self):
        return self.num_calc
    #
    # correct picture position
    #
    def prism(self,underlying_image, O, L, R, putative_angle, use_angle_correction=False):
        def fix_matrix(matrix):
            matrix[0,2] += (matrix[0,0] + matrix[0,1] - 1) / 2
            matrix[1,2] += (matrix[1,0] + matrix[1,1] - 1) / 2

            return matrix


        def get_angle(v, w):
            """
            Get the angle between vectors v and w

            :param v:
            :param w:
            :return:
            """

            return numpy.arccos(numpy.dot(v, w) / (numpy.sqrt(numpy.dot(v, v) * numpy.dot(w, w))))

        """
        Do the affine transform for the `underlying_image` defined by the maps the points O, L, R to O, L_, R_ correspondingly.

        :param underlying_image:
        :param O:
        :param L:
        :param R:
        :param use_angle_correction:
        :return:
        """

        if numpy.dot(L - O, L - O) > numpy.dot(R - O, R - O):
            v1 = L - O
            v2 = (R + L) / 2.0 - O
            v3 = v2 * numpy.dot(v1, v2) / numpy.dot(v2, v2)
            R_ = O + 2 * v3 - v1
            L_ = copy.copy(L) #L

            # shift_vector and vector are orthogonal
            length = numpy.sqrt(numpy.dot(v3, v3))
            shift_vector = v3 - v1
            shift_length = numpy.sqrt(numpy.dot(shift_vector, shift_vector))
            putative_length = shift_length / numpy.tan(putative_angle / 2.0)
            new_vector =  (1 - putative_length / length) * v3
        else:
            v1 = R - O
            v2 = (R - O + L - O) / 2.0
            v3 = v2 * numpy.dot(v1, v2) / numpy.dot(v2, v2)
            L_ = O + 2 * v3 - v1
            R_ = copy.copy(R) #R

            # shift_vector and vector are orthogonal
            length = numpy.sqrt(numpy.dot(v3, v3))
            shift_vector = v3 - v1
            shift_length = numpy.sqrt(numpy.dot(shift_vector, shift_vector))
            putative_length = shift_length / numpy.tan(putative_angle / 2.0)
            new_vector = (1 - putative_length / length) * v3

        if use_angle_correction:
            L_ += + new_vector
            R_ += + new_vector.astype(int)

        T = fix_matrix(cv2.getAffineTransform(
            src= numpy.asarray([L, O, R], dtype="float32"),
            dst=numpy.asarray([L_, O, R_], dtype="float32")
        ))

        cols, rows, channels = underlying_image.shape

        return cv2.warpAffine(underlying_image, T, (rows, cols), flags=cv2.INTER_LANCZOS4)

    def prism4(self,underlying_image, L, R, C, D, putative_angle, use_angle_correction=False):
        """

        :param underlying_image:
        :param use_angle_correction:
        :return:
        """

        # if numpy.dot(L - O, L - O) > numpy.dot(R - O, R - O):
        #     v1 = L - O
        #     v2 = (R + L) / 2.0 - O
        #     v3 = v2 * numpy.dot(v1, v2) / numpy.dot(v2, v2)
        #     R_ = O + 2 * v3 - v1
        #     L_ = copy.copy(L)
        # else:
        #     v1 = R - O
        #     v2 = (R - O + L - O) / 2.0
        #     v3 = v2 * numpy.dot(v1, v2) / numpy.dot(v2, v2)
        #     L_ = O + 2 * v3 - v1
        #     R_ = copy.copy(R)
        #
        # length = numpy.sqrt(numpy.dot(v3, v3))
        # shift_vector = v3 - v1
        # shift_length = numpy.sqrt(numpy.dot(shift_vector, shift_vector))
        # putative_length = shift_length / numpy.tan(putative_angle / 2.0)
        # new_vector = (1 - putative_length / length) * v3
        #
        # if use_angle_correction:
        #     L_ += + new_vector
        #     R_ += + new_vector
        #
        # T = fix_matrix(cv2.getAffineTransform(
        #     src=numpy.asarray([L, O, R], dtype="float32"),
        #     dst=numpy.asarray([L_, O, R_], dtype="float32")
        # ))
        #
        # cols, rows, channels = underlying_image.shape
        #
        # return cv2.warpAffine(underlying_image, T, (rows, cols), flags=cv2.INTER_LANCZOS4)
        O = (C + D) / 2.0
        A = (L + R) / 2.0 - O
        A2 = A / 2.0

        k = numpy.dot(A2, R - O) / numpy.dot(A2, A2) + 1
        R_ = A + R - k * A2 - A2

        k = numpy.dot(A2, L - O) / numpy.dot(A2, A2) + 1
        L_ = A + L - k * A2 - A2

        Z = R_ + A
        W = 2 * (O + A) - Z
        # W_ = L_ + A

        # cv2.line(image, tuple(map(int, O + A)), tuple(map(int, Z)), (0, 255, 0))
        # cv2.line(image, tuple(map(int, O + A)), tuple(map(int, W)), (0, 255, 0))

        k = numpy.dot(A2, D - O) / numpy.dot(A2, A2) + 1
        D_ = A + D - k * A2 - A2

        k = numpy.dot(A2, C - O) / numpy.dot(A2, A2) + 1
        # C_ = A + C - k * A2 - A2

        Z0 = D_
        W0 = 2 * (O + A) - Z0 - 2 * A

        # cv2.line(image, tuple(map(int, O)), tuple(map(int, Z0)), (0, 255, 0))
        # cv2.line(image, tuple(map(int, O)), tuple(map(int, W0)), (0, 255, 0))

        T = cv2.getPerspectiveTransform(
            src=numpy.asarray([L, R, C, D], dtype="float32"),
            dst=numpy.asarray([W, Z, W0, Z0], dtype="float32")
        )
        print('T=',T)
        cols, rows, channels = underlying_image.shape

        return cv2.warpPerspective(underlying_image, T, (rows, cols), flags=cv2.INTER_LANCZOS4)

    def prismu(self,underlying_image, points, putative_angle, use_angle_correction=False):
        """

        :param underlying_image:
        :param use_angle_correction:
        :return:
        """
        def get_angle(v, w):
            """
            Get the angle between vectors v and w

            :param v:
            :param w:
            :return:
            """

            return numpy.arccos(numpy.dot(v, w) / (numpy.sqrt(numpy.dot(v, v) * numpy.dot(w, w))))

        if len(points) == 4:
            L, R, C, D = points

            O = (C + D) / 2.0

            A = (L + R) / 2.0 - O
            A2 = A / 2.0

            k = numpy.dot(A2, R - O) / numpy.dot(A2, A2) + 1
            R_ = A + R - k * A2 - A2

            Z = R_ + A
            W = 2 * (O + A) - Z

            # cv2.line(image, tuple(map(int, O + A)), tuple(map(int, Z)), (0, 255, 0))
            # cv2.line(image, tuple(map(int, O + A)), tuple(map(int, W)), (0, 255, 0))

            k = numpy.dot(A2, D - O) / numpy.dot(A2, A2) + 1
            D_ = A + D - k * A2 - A2

            Z0 = D_
            W0 = 2 * (O + A) - Z0 - 2 * A

            # cv2.line(image, tuple(map(int, O)), tuple(map(int, Z0)), (0, 255, 0))
            # cv2.line(image, tuple(map(int, O)), tuple(map(int, W0)), (0, 255, 0))

            T = cv2.getPerspectiveTransform(
                src=numpy.asarray([L, R, C, D], dtype="float32"),
                dst=numpy.asarray([W, Z, W0, Z0], dtype="float32")
            )
            #print('T=',T,'DET:DIAG',numpy.linalg.det(T),sum(numpy.diag(T)))
            cols, rows, channels = underlying_image.shape
            #####
            if use_angle_correction:
                real_angle = get_angle(W - (W0 + Z0) / 2.0, Z - (W0 + Z0) / 2.0)
                contracting = list((real_angle / putative_angle) * A / numpy.sqrt(numpy.dot(A, A)))
                if numpy.prod(list(map(abs, contracting))) < 0.1:
                    contracting[0] = 1 + abs(contracting[0])
                    contracting[-1] = abs(contracting[-1])

                    underlying_image = cv2.warpPerspective(underlying_image, T, (rows, cols), flags=cv2.INTER_LANCZOS4)
                    return cv2.warpAffine(underlying_image, numpy.asarray([[contracting[0], 0, 0], [0, contracting[1], 0]], dtype="float32"), (rows, cols), flags=cv2.INTER_LANCZOS4)
            underlying_image = cv2.warpPerspective(underlying_image, T, (rows, cols), flags=cv2.INTER_LANCZOS4)
            #print("warpPerspective OK")
            return underlying_image
            #####

        else:
            L, R, O = points

            if numpy.dot(L - O, L - O) > numpy.dot(R - O, R - O):
                v1 = L - O
                v2 = (R + L) / 2.0 - O
                v3 = v2 * numpy.dot(v1, v2) / numpy.dot(v2, v2)
                R_ = O + 2 * v3 - v1
                L_ = copy.copy(L)
            else:
                v1 = R - O
                v2 = (R - O + L - O) / 2.0
                v3 = v2 * numpy.dot(v1, v2) / numpy.dot(v2, v2)
                L_ = O + 2 * v3 - v1
                R_ = copy.copy(R)

            length = numpy.sqrt(numpy.dot(v3, v3))
            shift_vector = v3 - v1
            shift_length = numpy.sqrt(numpy.dot(shift_vector, shift_vector))
            putative_length = shift_length / numpy.tan(putative_angle / 2.0)
            new_vector = (1 - putative_length / length) * v3

            if use_angle_correction:
                L_ += + new_vector
                R_ += + new_vector

            T = fix_matrix(cv2.getAffineTransform(
                src=numpy.asarray([L, O, R], dtype="float32"),
                dst=numpy.asarray([L_, O, R_], dtype="float32")
            ))

            cols, rows, channels = underlying_image.shape

            return cv2.warpAffine(underlying_image, T, (rows, cols), flags=cv2.INTER_LANCZOS4)

    def distortion(self,image,L,R,E):
        def fix_matrix(matrix):
            matrix[0,2] += (matrix[0,0] + matrix[0,1] - 1) / 2
            matrix[1,2] += (matrix[1,0] + matrix[1,1] - 1) / 2

            return matrix
        # E = numpy.asarray((702.50, 64.00))    # 1
        E_ = (L + R) / 2.0

        center = numpy.asarray((image.shape[1], image.shape[0])) / 2.0
        # simple distortion compensation
        # ------------------------------------------------------------------------------------------------------------------
        Lx, Ly = L
        Rx, Ry = R
        Cx, Cy = center
        Ex, Ey = E
        l = (Cx*Ey - Ex*Cy - Rx *(Ey-Cy) - Ry*(Cx-Ex)) / ((Lx - Rx)*(Ey-Cy) + (Ly-Ry)*(Cx-Ex))
        E__ = l * L + (1-l) * R

        T = fix_matrix(cv2.getAffineTransform(
            src=numpy.asarray([L, center, E], dtype="float32"),
            dst=numpy.asarray([L, center, E__], dtype="float32")
        ))

        cols, rows, channels = image.shape
        return cv2.warpAffine(image, T, (rows, cols), flags=cv2.INTER_LANCZOS4)


    # get points of triangle
    def get_triangle_xy(self,list = [0,1,2]):
        points_xy,circle_tp = [],[]
        off_8 = 0 # position offset for case when some kind of circles were lost
        off_4 = -1
        shift = self.OBJ_H*3
        for v in self.circles_grid:
            if len(v) > 6:
                break
            else: # small circles
                if off_4 == -1:
                    (x,y),_,_ = self.get_fit_ellipse(v[0])
                    if abs(y-self.MIN_GRID_Y) > shift:
                        off_4 = off_8
            off_8 += 1
        #print('offset for 8:4',off_8,off_4)
        for n in list:
            try:
                if n > 5:
                   n = off_8 + (n - 6)
                elif n > 2: # ask bottom line
                   n = off_4 + (n - 3)
                v = self.circles_grid[n]
            except:
                break
            (x,y),_,_ = self.get_fit_ellipse(v[0])
            points_xy.append([x,y])
            circle_tp.append(True if len(v) > 4 else False)
        return points_xy,circle_tp
    #
    # draw triangle using position into circle's grid
    def draw_base_triangle(self,image,list = [0,1,2]):
        points_xy,_ = self.get_triangle_xy(list)
        if len(points_xy) > 2:
            #print('points_xy',points_xy)
            points = np.array(points_xy)
            cv2.polylines(image, np.int32([points]), 1, (0,255,255))
            #print('draw_base_triangle OK')
    def is_point_for_prism(self,tp,xy):
        shift = self.OBJ_H*3

        return tp[0] or tp[1] or not tp[2] or not tp[3] or abs(xy[1][0]-xy[0][0]) < shift or abs(xy[3][0]-xy[2][0]) < shift or abs(xy[3][1]-xy[2][1]) > shift or abs(xy[1][1]-xy[0][1]) > shift
    #
    # correct base picture position
    #
    def base_pict2prism(self,image,is_angle = False,is_distor = False,verb=True):

        if len(self.circles_grid) < 10:
            if verb:
                print('not enought circles into grid')
            return image,False
        points_xy,circle_tp = self.get_triangle_xy([0,2,6,7,1]) # [0,2,3,4]
        min_num = 5 if is_distor else 4
        if len(points_xy) < min_num or self.is_point_for_prism(circle_tp,points_xy) or (is_distor and circle_tp[4]):
            if verb:
                print('SKIP BASE CIRCLES arranged wrong',circle_tp)
            return image,False
        num = len(points_xy)
        A = 2.5836568532645083 # 1.4355661144896756 # 1.47 #1.1541716899334
        L = numpy.asarray(points_xy[0]) #
        R = numpy.asarray(points_xy[1]) #
        if is_distor:
            if self.dist is None:
                E = numpy.asarray(points_xy[4])
                image = self.distortion(image,L,R,E)
            else:
                #use chequer
                image = self.dist.undistort(image)

        if num >= 4:
            C = numpy.asarray(points_xy[2]) #
            D = numpy.asarray(points_xy[3])
            #O = numpy.asarray([(points_xy[2][0]+points_xy[3][0])/2.0,(points_xy[2][1]+points_xy[3][1])/2.0])
            image = self.prismu(image,[L,R,C,D],A,is_angle)
            #print('base_pict2prism prism OK')
            return image,True
        elif num == 3:
            O = numpy.asarray(points_xy[2])
            return self.prism(image, O, L, R, A,is_angle),True
        else:
            return image,False


    def lens_pict2prism(self,image,is_angle = False,verb = True):
        num_point = len(self.circles_grid)
        if num_point < 10:
            if verb:
                print('not enought circles into grid')
            return image,False
        points_xy,circle_tp = self.get_triangle_xy([3,5,8,9])
        #print('lens_pict2prism:points',num_point,circle_tp,points_xy)
        if len(circle_tp) < 4 or self.is_point_for_prism(circle_tp,points_xy):
            if verb:
                print('SKIP LENS CIRCLES arranged wrong',circle_tp)
            return image,False
        num = len(points_xy)
        A = 2.5836568532645083 # 1.4355661144896756 # 1.47 #1.1541716899334
        L = numpy.asarray(points_xy[0]) #
        R = numpy.asarray(points_xy[1]) #
        if num >= 4:
            C = numpy.asarray(points_xy[2]) #
            D = numpy.asarray(points_xy[3])
            #O = numpy.asarray([(points_xy[2][0]+points_xy[3][0])/2.0,(points_xy[2][1]+points_xy[3][1])/2.0])
            #print('lens_pict2prism ..')
            image = self.prismu(image,[L,R,C,D],A,is_angle)
            #print('lens_pict2prism OK')
            return image,True
        elif num == 3:
            O = numpy.asarray(points_xy[2])
            return self.prism(image, O, L, R, A,is_angle),True
        else:
            return image,False

    #
    #  process image
    #
    def processing_image(self,frame,counter):
        #global circles_grid,position_quality,is_lens_appeared,lens_group,base_group,args
        self.select_circles_grid(frame,counter)
        #print('process',counter,'grid',len(self.circles_grid))
        #self.position_quality,self.is_lens_appeared = False,False
        if self.check_lens_presence() > 1 :
            self.calc_lens()

        if self.show_grid_for_scan_mode :
            frame = self.draw_grid(frame)
        if self.show_frame_num:
            cv2.putText(frame,"FRAME="+str(counter)+" GRID="+str(len(self.circles_grid)), (150,150), cv2.FONT_HERSHEY_SIMPLEX, 0.89, (80,100,30), 2)
        return frame,self.position_quality,self.is_lens_appeared

    #
    #  process image with prism correction
    #
    def processing_image_with_prism(self,frame,counter,with_angle = True,with_distor=True):
        # select circles before first step correction
        self.select_circles_grid(frame,counter)
        frame,was_correct = self.base_pict2prism(frame, with_angle, with_distor,False )
        num_calc = self.num_calc
        print('frame,was_correct', frame,was_correct)
        if was_correct:
            # select circles again
            self.select_circles_grid(frame,counter)
            self.set_base_circles()
            frame,was_lens_correct = self.lens_pict2prism(frame, False,False )
            if was_lens_correct: # it's mean that circles under lens were found
                self.select_circles_grid(frame,counter)
                if self.check_lens_presence2() > 1 :
                    self.calc_lens()
        is_dset = False
        self.is_lens_appeared = False if num_calc == self.num_calc else True
        if self.is_calc_interrupted(num_calc):
            is_dset = self.reset_calc()  # series was interrupted
        if self.show_grid_for_scan_mode :
            frame = self.draw_grid(frame)
        if self.show_frame_num:
            cv2.putText(frame,"FRAME="+str(counter)+" GRID="+str(len(self.circles_grid)), (150,150), cv2.FONT_HERSHEY_SIMPLEX, 0.89, (80,100,30), 2)
        return frame,self.position_quality,self.is_lens_appeared,is_dset

#
#   save params for dataset
#
    def save_distort(self,name,protocol=None):
        #save distort and focus params
        if name != "":
            dict = {} if self.dist is None else self.dist.get_dict_distort()
            # add focus and pixsz
            dict['campix'] = self.cam_pix_sz
            dict['monpix'] = self.mon_pix_sz
            dict['objh']   = self.OBJ_H
            with open(os.getenv("HOME") + '/tmp/' + name+'.distort', 'wb') as f:
                pickle.dump(dict, f,protocol)

#
#
#
    def load_distort(self,name):
        # load dset params
        dirnm = os.path.dirname(name)
        base = os.path.basename(name)
        base = os.path.splitext(base)
        print('path',dirnm,'base',base[0])
        fname = (dirnm + '/' if dirnm != '' else '') +  base[0] + '.distort'
        try:
            with open(fname, 'rb') as f:
                dict = pickle.load(f)
            print('dict',dict)
            # set
            if 'newcameramtx' in dict:
                dist = Distort()
                dist.set_distort(dict)
                self.set_distort_table(dist)
            if 'campix' in dict:
                self.cam_pix_sz = dict['campix']
            if 'monpix' in dict:
                self.mon_pix_sz = dict['monpix']
            if 'objh' in dict:
                self.OBJ_H = dict['objh']

            self.H = self.mon_pix_sz * self.OBJ_H
            print('H',self.H,'campix',self.cam_pix_sz,'monpix',self.mon_pix_sz)
        except :
            print('Cant load distort')
            print_exc()


#
# make dataset
#
class Dataset():
    def __init__(self):
        self.dset_fd = None  # for dset
        self.dset_process = False  #
        self.width,self.height = None,None
        self.dset_fnum = 0
        self.calc_num  = 0
        self.mesure_mode = False

    def open_dset(self,dset_nm,width,height,codec="XVID"):
        if self.mesure_mode or self.dset_fd is not None:
            return False

        self.dset_nm = dset_nm
        if dset_nm != "":
            # open dset
            fnm = os.getenv("HOME") + '/tmp/' + dset_nm + ".avi" #(".avi" if codec == "XVID" else ".mjpg")
            fd = cv2.VideoWriter(fnm, cv2.VideoWriter_fourcc(*codec), float(25),(width,height),True) # "MJPG" "XVID"
            self.width,self.height = width,height
            if fd is None:
                print('Cant open file for write',fnm)
            else:
                print('Open DSET into',fnm,'size',(width,height))
                self.dset_fd = fd

        else:
            print('Open DSET into mesure mode')
            self.mesure_mode = True
        self.dset_fnum,self.dset_process,self.calc_num = 0,True,0
        return True



    def is_open_dset(self):
        return self.mesure_mode or self.dset_fd is not None

    def get_dset_name(self):
        return self.dset_nm

    def ask_close_dset(self):
        #if self.dset_fd is not None:
        print('ASK STOP',self.mesure_mode)
        if self.mesure_mode:
            self.close_dset()
        else:
            self.dset_process = False
    def get_dset_num(self):
        return self.dset_fnum

    def get_calc_num(self):
        return self.calc_num

    def add_frame_into_dset(self,frame,lens_appeared = True):
        if lens_appeared:
            self.calc_num += 1

        if self.dset_fd is not None:
            if self.dset_process == False: # ask stop
                self.close_dset()
                return
            try:
                fr1 = cv2.resize(frame,(self.width,self.height))
                self.dset_fd.write(fr1)
                self.dset_fnum +=1
                #print('add frame into dset',self.dset_fnum,self.dset_process)
                #if self.dset_fnum > 100:
                #    self.close_dset()
            except :
                print_exc()
                self.close_dset()
        else:
            self.dset_fnum +=1


    def close_dset(self):
        if self.dset_fd is not None:
            self.dset_fd.release()
            self.dset_fd = None
            print("close_dset: OK",self.dset_fnum)
            self.dset_fnum = 0
        elif self.mesure_mode :
            self.dset_fnum = 0
            self.mesure_mode = False
            print("close_dset: MESURE EOF")
        else:
            print("close_dset: ALREADY CLOSED")


#
# for distortion
#
class Distort:
    def __init__(self,min_num = 10):
        self.min_for_distort = min_num
        self.calc_num  = 0
        self.mesure_mode = False
        self.criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
        self.objp = np.zeros((6*7,3), np.float32)
        self.objp[:,:2] = np.mgrid[0:7,0:6].T.reshape(-1,2)
        # Arrays to store object points and image points from all the images.
        self.objpoints = [] # 3d point in real world space
        self.imgpoints = [] # 2d points in image plane.

    def open_dset(self,name):
        if self.mesure_mode:
            return False
        self.calc_num  = 0
        self.mesure_mode = True
        self.dset_name = name
        self.objpoints = [] # 3d point in real world space
        self.imgpoints = [] # 2d points in image plane.
        self.mtx, self.dist,self.newcameramtx = None,None,None
        print('Open distort',name)
        return True

    def is_open_dset(self):
        return self.mesure_mode

    def add_frame_into_dset(self,img):
        self.gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Find the chess board corners
        ret, corners = cv2.findChessboardCorners(self.gray, (7,6), None)
        # If found, add object points, image points (after refining them)
        print('add_frame::findChessboardCorners::',ret,self.calc_num)
        if ret == True:
            self.objpoints.append(self.objp)
            self.imgpoints.append(corners)
            self.calc_num  += 1
        return ret
            #corners2 = cv2.cornerSubPix(gray,corners, (11,11), (-1,-1), self.criteria)
            # Draw and display the corners
            #cv2.drawChessboardCorners(img, (7,6), corners2, ret)

    def close_dset(self,force = False):
        ret = False
        if self.is_dset_ready() or (force and self.calc_num > 0):
            # make distortion table
            ret, self.mtx, self.dist, rvecs, tvecs = cv2.calibrateCamera(self.objpoints, self.imgpoints, self.gray.shape[::-1], None, None)
            if ret:

                # undistor
                h,  w = self.gray.shape[:2]
                self.newcameramtx, roi = cv2.getOptimalNewCameraMatrix(self.mtx, self.dist, (w,h), 1, (w,h))
                #print('calibrateCamera: WAS DONE',ret,'mtx', self.mtx,'dist', self.dist,'newcameramtx',self.newcameramtx) # rvecs, tvecs)
                print('calibrateCamera: WAS DONE')
                # save distort
                self.save_distort(self.dset_name)
                ret = True
        self.gray = None
        self.calc_num  = 0
        self.mesure_mode = False
        return ret

    def is_dset_ready(self):
        return self.calc_num > self.min_for_distort

    def get_calc_num(self):
        return self.calc_num

    def get_dict_distort(self):
        return {'mtx':self.mtx,'dist':self.dist,'newcameramtx':self.newcameramtx}

    def set_distort(self,dict):
        self.mtx,self.dist,self.newcameramtx = dict['mtx'],dict['dist'],dict['newcameramtx']

    def save_distort(self,name):
        if name != "":
            distort = self.get_dict_distort()
            with open(os.getenv("HOME") + '/tmp/' + name+'.distort', 'wb') as f:
                pickle.dump(distort, f)
            #print('check loading')
            #self.load_distort(self.dset_name)

    def load_distort(self,name):
        try:
            fname = name if name[0:1] == '/' else (os.getenv("HOME") + '/tmp/' + name)
            with open(fname + '.distort', 'rb') as f:
                data = pickle.load(f)
            print('loaded distort:mtx',data['mtx'],'dist',data['dist'],'newcameramtx',data['newcameramtx'])
            self.mtx, self.dist,self.newcameramtx = data['mtx'],data['dist'],data['newcameramtx']
        except :
            print('Cant load distort from file')


    def undistort(self,img):
        if self.mtx is None:
            return img
        print('undistort by chequer')
        dst = cv2.undistort(img, self.mtx, self.dist, None, self.newcameramtx)
        return dst

#
# for testing
if __name__ == '__main__':
    print('take frame from usbcam or files.Params',def_conf)


