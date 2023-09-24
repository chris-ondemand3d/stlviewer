"""
stl view & get view vector & get point set
"""

# Assume input surface model (sometimes with a hole)
#
#

import sys
import os
import time
import datetime
import math
#import threading
import json

import PyQt5.QtGui
from PyQt5.QtGui import QOpenGLWindow
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QOpenGLWidget, QSlider, QWidget)
from PyQt5.QtCore import pyqtSignal, QPoint, QSize, QRect, Qt
from PyQt5 import Qt, QtCore, QtWidgets
from PyQt5.Qt import QPushButton, QHBoxLayout, QVBoxLayout, QTextEdit, QApplication, QLineEdit, QLabel, QFileDialog, QCheckBox

#import pygame
import vtk
import OpenGL
#from OpenGL.GL import *
#from OpenGL.GLU import *
from OpenGL.GLUT import *
import CyMesh
#import CyOffset
import MeshWorks

import numpy as np
from vtk.util.numpy_support import vtk_to_numpy
 
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


class GLWindow(QOpenGLWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gl = None

    def sizeHint(self):
        return QSize(400, 400)

    def initializeGL(self):
        version = PyQt5.QtGui.QOpenGLVersionProfile()
        version.setVersion(2, 1)
        self.gl = self.context().versionFunctions(version)
        self.gl.initializeOpenGLFunctions()
        self.gl.glShadeModel(self.gl.GL_FLAT)
        self.gl.glEnable(self.gl.GL_DEPTH_TEST)
        self.gl.glEnable(self.gl.GL_CULL_FACE)

    def paintGL(self):
        self.gl.glClear(self.gl.GL_COLOR_BUFFER_BIT | self.gl.GL_DEPTH_BUFFER_BIT)

    def resizeGL(self, width, height):
        side = min(width, height)
        if side < 0: return
        self.gl.glViewport((width - side) // 2, (height - side) // 2, side, side)


class MyContourWidget(vtk.vtkContourWidget):
    def __init__(self):
        super().__init__()

        self.AddObserver("StartInteractionEvent",self.ProcessEvent)
        self.AddObserver("InteractionEvent", self.ProcessEvent)
        self.AddObserver("EndInteractionEvent", self.ProcessEvent)

    def ProcessEvent(self, object, event):
        print(event)
        if (event==vtk.vtkCommand.StartInteractionEvent):
            print("Start Interaction")
        elif (event==vtk.vtkCommand.InteractionEvent):
            print("Interaction")
        elif (event==vtk.vtkCommand.EndInteractionEvent):
            print("EndInteraction")


class Viewer():
    def __init__(self, stl_file, width, height):
        super().__init__()

        # for repair
        self.l1 = 1
        self.l2 = 1
        self.l3 = 1

        # Contour widget
        self.contourMarked = 0

        # marker set
        self.POINT_SET = []
        self.MARKER_SET = []
        self.CameraPos_Set = []
        self.FocalPoint_Set = []
        self.UpVector_Set = []

        # new marker id
        self.new_marker_id = 0
        self.Camera_id = 0

        reader = vtk.vtkSTLReader()
        reader.SetFileName(stl_file)
        reader.MergingOn()
        reader.Update()

        print(reader.GetOutput().GetNumberOfPoints(),reader.GetOutput().GetNumberOfPolys())

#       VTK cleaner filter isn't good enough many mesh problems
#        self.cleaner = vtk.vtkCleanPolyData()
#        self.cleaner.SetInputConnection(self.reader.GetOutputPort())
#        self.cleaner.Update()

        self.originalData = vtk.vtkPolyData()
        self.data = vtk.vtkPolyData()
        self.originalData = reader.GetOutput()
# expecting just reference
        self.data = self.originalData

        self.nOrigPolys = self.data.GetNumberOfPolys()
        self.nOrigPoints = self.data.GetNumberOfPoints()

        self.Colors = vtk.vtkUnsignedCharArray()
        self.Colors.SetNumberOfComponents(3)
        self.Colors.SetName("Colors")
        self.Marked = vtk.vtkUnsignedIntArray()
        self.Marked.SetNumberOfComponents(1)
        self.Marked.SetName("Marked")

        for i in range(0,self.nOrigPolys):
            self.Marked.InsertNextTuple1((0))
            self.Colors.InsertNextTuple3(128,128,128)
        self.data.GetCellData().SetScalars(self.Colors)

# Todo VTK version of repair later
# Remove Non-manifold cell
#        self.CleanNonmanifoldCell()
#        self.CleanSimplexVertex()
# Remove Simplex face
#        self.CleanSimplexFace(4)

        self.mapper = vtk.vtkPolyDataMapper()
        self.mapper.SetInputData(self.data)

        self.actor = vtk.vtkActor()
        self.actor.SetMapper(self.mapper)

# Test
        self.viewArrow = vtk.vtkArrowSource()

        # Create a rendering window and renderer
        self.ren = vtk.vtkRenderer()
        self.renWin = vtk.vtkRenderWindow()

        self.renWin.AddRenderer(self.ren)
        # Assign actor to the renderer
        self.ren.AddActor(self.actor)

        # Create a renderwindowinteractor
        self.iren = vtk.vtkRenderWindowInteractor()
#        istyle = vtk.vtkInteractorStyleTrackballCamera()
        self.iren.SetInteractorStyle(None)
        self.iren.SetRenderWindow(self.renWin)

        # set color (not in use, use each face coloring )
        forProp = vtk.vtkProperty()
        #backProp = vtk.vtkProperty()
        forProp.SetColor([175/255, 175/255, 175/255])
        #self.actor.SetProperty(forProp)
        #backProp.SetColor([.0,.0, 175/255])
        #self.actor.SetBackfaceProperty(backProp)

        # picker
        self.locator = vtk.vtkCellLocator()
        self.picker = vtk.vtkCellPicker()
        self.iren.SetPicker(self.picker)

        # Locator
        self.locator.SetDataSet(self.data)
        self.locator.BuildLocator()
        self.picker.AddLocator(self.locator)

        # I do not know why clipping applied too tight, however expand clip box two times
        self.ren.ResetCamera()
        fBound = [.0, .0 , .0, .0, .0, .0]
        self.ren.ComputeVisiblePropBounds(fBound)
        fBound[0] = fBound[0]-(fBound[1]-fBound[0])/2
        fBound[1] = fBound[1]+(fBound[1]-fBound[0])/2
        fBound[2] = fBound[2]-(fBound[3]-fBound[2])/2
        fBound[3] = fBound[3]+(fBound[3]-fBound[2])/2
        fBound[4] = fBound[4]-(fBound[5]-fBound[4])/2
        fBound[5] = fBound[5]+(fBound[5]-fBound[4])/2
        self.ren.ResetCameraClippingRange(fBound)

        self.Rotating = 0
        self.Panning = 0
        self.Zooming = 0
        self.Marking = 0

        self.mode = 0    # Open STL file

        self.iren.AddObserver("LeftButtonPressEvent", self.ButtonEvent)
        self.iren.AddObserver("LeftButtonReleaseEvent", self.ButtonEvent)
        self.iren.AddObserver("MiddleButtonPressEvent", self.ButtonEvent)
        self.iren.AddObserver("MiddleButtonReleaseEvent", self.ButtonEvent)
        self.iren.AddObserver("RightButtonPressEvent", self.ButtonEvent)
        self.iren.AddObserver("RightButtonReleaseEvent", self.ButtonEvent)
        self.iren.AddObserver("MouseMoveEvent", self.MouseMove)
        self.iren.AddObserver("KeyPressEvent", self.Keypress)

        if height > (width-400)*0.75:
            height = int((width-400)*0.75)
        self.height = height
        self.width = width-400
        self.renWin.SetSize(width-400, height)

        # make sphere for marking
        self.sphere = vtk.vtkSphere()
        self.sphereRadius = 2
        self.sphere.SetRadius(self.sphereRadius)
        self.viewArrow = vtk.vtkArrowSource()
        self.viewArrow.SetTipResolution(25)
        self.viewArrow.SetShaftResolution(25)

        self.mode = 0

    def set_point_tree(self, tree_view):
        self.tree_view = tree_view

    def clean(self):
        if self.new_marker_id !=0:
            del self.POINT_SET[0:self.new_marker_id]
            del self.MARKER_SET[0:self.new_marker_id]
            del self.POINT_SET
            del self.MARKER_SET
        self.new_marker_id = 0

        del self.picker
        del self.locator
        del self.sphere
        del self.viewArrow

        # remove countourWidget, boxWidget
        if hasattr(self,"MyContourWidget"):
            del self.MyContourWidget
        if hasattr(self,"boxWidget"):
            del self.boxWidget
        # Cleanup in case terminate in mode 4
        if self.mode == 4:
            del self.arrowMapper
            del self.arrowActor
 #           del self.planes

        if hasattr(self, 'data'):
            del self.mapper
            for i in range(0,self.data.GetNumberOfPolys()):
                self.Marked.RemoveLastTuple()
                self.Colors.RemoveLastTuple()
            del self.Marked
            del self.Colors
            del self.data
            del self.originalData
            print("Remove data")
        if hasattr(self, 'repairedData'):
            del self.repairedData
            print("Remove repairedData")
        if hasattr(self, 'extrudedData'):
            del self.extrudedData
            print("Remove extrudedData")
        if hasattr(self, 'offsetedModel'):
            del self.offsetedModel
            print("Remove offsetedModel")

        del self.actor
        del self.ren
        del self.iren
        del self.renWin

    def save_all(self,destDir):
        stlWriter = vtk.vtkSTLWriter()
        if hasattr(self, 'data'):
            stlWriter.SetFileName(destDir+"\originalData.stl")
            stlWriter.SetInputData(self.originalData)
            stlWriter.SetFileTypeToBinary()
            stlWriter.Write()
            print("save data to "+destDir+"\data.stl")
        if hasattr(self, 'repairedData'):
            stlWriter.SetFileName(destDir+'\\repairedData.stl')
            stlWriter.SetInputData(self.repairedData)
            stlWriter.SetFileTypeToBinary()
            stlWriter.Write()
            print("save repairedData to "+destDir+"\\repairedData.stl")
        if hasattr(self, 'extrudedData'):
            stlWriter.SetFileName(destDir+"\extrudededData.stl")
            stlWriter.SetInputData(self.extrudedData)
            stlWriter.SetFileTypeToBinary()
            stlWriter.Write()
            print("save extrudedData to "+destDir+"\\extrudedData.stl")
        if hasattr(self, 'offsetedModel'):
            stlWriter.SetFileName(destDir+"\offsetedModel")
            stlWriter.SetInputData(self.offsetedModel)
            stlWriter.SetFileTypeToBinary()
            stlWriter.Write()
            print("save offsetedModel  to "+destDir+"\\offsetedModel.stl")
        if self.Camera_id > 0:
            CamFile = open("Camera.json",'w')
            data=[]
            for i in range(self.Camera_id):
                pos = self.CameraPos_Set[i]
                fp = self.FocalPoint_Set[i]
                up_vec = self.UpVector_Set[i]
                data.append({'id':i,'camerapos':pos, 'focalpoint':fp, "up_vec": up_vec })
            s={"camera": data}
            json.dump(s,CamFile)
            CamFile.close()

    def loadCamera(self):
        CamFile = open("Camera.json", 'r')
#        print(CamFile.read()[0:100])
        s = json.load(CamFile)
        data = s["camera"]

        for j in range(len(data)):
            i = data[j]['id']
            pos = data[j]['camerapos']
            fp = data[j]['focalpoint']
            up_vec = data[j]['up_vec']

            self.CameraPos_Set.append(pos)
            self.FocalPoint_Set.append(fp)
            self.UpVector_Set.append(up_vec)

            row = Qt.QTreeWidgetItem(self.tree_view)
            row.setText(0, str(self.Camera_id))
            self.Camera_id += 1
            row.setTextAlignment(0, QtCore.Qt.AlignLeft)
            row.setText(1, str(pos))
            row.setText(2, str(fp))
            row.setText(3, str(up_vec))

        CamFile.close()

    # Coloring face and maxlevel-adjacent faces by color (Breadth First Search)
    def Redmark(self, i, maxlevel, color):
        self.data.BuildLinks()
        ptIds = vtk.vtkIdList()
        neighborCellIds = vtk.vtkIdList()
        # starting face i
        levellist = []
        levellist.append(i)
        self.Colors.SetComponent(i, 0, 128)
        self.Colors.SetComponent(i, 1, 0)
        self.Colors.SetComponent(i, 2, 0)

        for level in range(1, maxlevel):
            facelist = []
            while len(levellist) != 0:
                i = levellist.pop()
                self.data.GetCellPoints(i, ptIds)
                print("Redmark: ", i,ptIds.GetId(0),ptIds.GetId(1),ptIds.GetId(2))
                self.data.GetCellEdgeNeighbors(i, ptIds.GetId(0), ptIds.GetId(1), neighborCellIds)
                for j in range(0, neighborCellIds.GetNumberOfIds()):
                    if facelist.count(neighborCellIds.GetId(j))==0: facelist.append(neighborCellIds.GetId(j))
                    self.Colors.SetComponent(neighborCellIds.GetId(j), 0, color[0])
                    self.Colors.SetComponent(neighborCellIds.GetId(j), 1, color[1])
                    self.Colors.SetComponent(neighborCellIds.GetId(j), 2, color[2])

                self.data.GetCellEdgeNeighbors(i, ptIds.GetId(1), ptIds.GetId(2), neighborCellIds)
                for j in range(0, neighborCellIds.GetNumberOfIds()):
                    if facelist.count(neighborCellIds.GetId(j)) == 0: facelist.append(neighborCellIds.GetId(j))
                    self.Colors.SetComponent(neighborCellIds.GetId(j), 0, color[0])
                    self.Colors.SetComponent(neighborCellIds.GetId(j), 1, color[1])
                    self.Colors.SetComponent(neighborCellIds.GetId(j), 2, color[2])

                self.data.GetCellEdgeNeighbors(i, ptIds.GetId(2), ptIds.GetId(0), neighborCellIds)
                for j in range(0, neighborCellIds.GetNumberOfIds()):
                    if facelist.count(neighborCellIds.GetId(j)) == 0: facelist.append(neighborCellIds.GetId(j))
                    self.Colors.SetComponent(neighborCellIds.GetId(j), 0, color[0])
                    self.Colors.SetComponent(neighborCellIds.GetId(j), 1, color[1])
                    self.Colors.SetComponent(neighborCellIds.GetId(j), 2, color[2])

            if (len(facelist)>0): levellist = facelist
            else: levelist = []

    # Handle the mouse button events.
    def ButtonEvent(self, iren, event):

        if event == "RightButtonPressEvent":
            self.Rotating = 1
        elif event == "RightButtonReleaseEvent":
            self.Rotating = 0
        elif event == "MiddleButtonPressEvent":
            self.Zooming = 1
        elif event == "MiddleButtonReleaseEvent":
            self.Zooming = 0

        if self.mode == 1 or self.mode == 6: # in case lef button press on model, re-enter contourWidget
            xypos = self.iren.GetEventPosition()
            x = xypos[0]
            y = xypos[1]
            self.picker.Pick(x, y, 0, self.ren)
            pickPos = self.picker.GetPickPosition()
            if (self.picker.GetCellId() != -1):
                if event == "LeftButtonPressEvent":
                    self.MyContourWidget.SetWidgetState(1)
                elif event == "RightButtonPressEvent":
                    self.MyContourWidget.CloseLoop()
                    self.MarkContour1(x,y,pickPos)

        elif self.mode == 2 :
            if event == "LeftButtonPressEvent":
                self.Marking = 1
                # Faster interaction(marking is more responsive)
                xypos = self.iren.GetEventPosition()
                x = xypos[0]
                y = xypos[1]
                self.pickMark(x,y)
            elif event == "LeftButtonReleaseEvent":
                self.Marking = 0
                #    self.ren.RemoveActor(self.clipActor)
        else:
            if event == "LeftButtonPressEvent":
                self.Panning = 1
            elif event == "LeftButtonReleaseEvent":
                self.Panning = 0

        self.renWin.Render()


    def MouseMove(self, iren, event):
        lastXYpos = self.iren.GetLastEventPosition()
        lastX = lastXYpos[0]
        lastY = lastXYpos[1]

        xypos = self.iren.GetEventPosition()
        x = xypos[0]
        y = xypos[1]

        if self.mode == 4:
            renderer = self.iren.FindPokedRenderer(x,y)
            center = self.renWin.GetSize()
            if renderer == self.ren:
                centerX = center[0] / 4.0
            else:
                centerX = center[0]*3.0/4.0
            centerY = center[1] / 2.0

            if self.Rotating:
                self.Rotate(renderer, renderer.GetActiveCamera(), x, y, lastX, lastY, centerX, centerY)
            elif self.Panning:
                self.Pan(renderer, renderer.GetActiveCamera(), x, y, lastX, lastY, centerX, centerY)
            elif self.Zooming:
                self.Dolly(renderer, renderer.GetActiveCamera(), x, y, lastX, lastY, centerX, centerY)
        else:
            center = self.renWin.GetSize()
            centerX = center[0] / 2.0
            centerY = center[1] / 2.0

            if self.Rotating:
                self.Rotate(self.ren, self.ren.GetActiveCamera(), x, y, lastX, lastY, centerX, centerY)
            elif self.Panning:
                self.Pan(self.ren, self.ren.GetActiveCamera(), x, y, lastX, lastY, centerX, centerY)
            elif self.Zooming:
                self.Dolly(self.ren, self.ren.GetActiveCamera(), x, y, lastX, lastY, centerX, centerY)
            elif self.Marking:
                self.pickMark(x, y)

    # Contour Widget for Trimming
    def contourPick(self):

        for i in range(self.data.GetNumberOfPolys()):
            self.Colors.SetComponent(i, 0, 128)
            self.Colors.SetComponent(i, 1, 128)
            self.Colors.SetComponent(i, 2, 128)
            self.Marked.SetValue(i, 0)

        # Here comes the contour widget stuff
        if hasattr(self,"MyContourWidget")==False:
            self.MyContourWidget = MyContourWidget()
            self.MyContourWidget.SetInteractor(self.iren)

            rep = vtk.vtkOrientedGlyphContourRepresentation()
            rep = self.MyContourWidget.GetRepresentation()
            rep.GetLinesProperty().SetColor(1, 0.2, 0)
            rep.GetLinesProperty().SetLineWidth(5.0)

            pointPlacer = vtk.vtkPolygonalSurfacePointPlacer()
            pointPlacer.AddProp(self.actor)
            pointPlacer.GetPolys().AddItem(self.data)
            rep.SetPointPlacer(pointPlacer)

            interpolator = vtk.vtkPolygonalSurfaceContourLineInterpolator()
#            interpolator = vtk.vtkLinearContourLineInterpolator()
#            interpolator = vtk.vtkBezierContourLineInterpolator()
            interpolator.GetPolys().AddItem(self.data)
            rep.SetLineInterpolator(interpolator)

            self.MyContourWidget.FollowCursorOff()
            self.MyContourWidget.ContinuousDrawOff()
        else:
            # Clear data point
            self.MyContourWidget.EnabledOn()
            self.MyContourWidget.GetContourRepresentation().ClearAllNodes()
            self.MyContourWidget.Initialize()

        self.MyContourWidget.EnabledOn()
        self.contourMarked=0
        print("Contour Widget Enabled",id(self.MyContourWidget))


    #Initialize for start marking
    def startMark(self):

        self.idFilter = vtk.vtkIdFilter()
        self.idFilter.SetInputData(self.data)
        self.idFilter.SetIdsArrayName("OriginalIds")
        self.idFilter.Update()

        self.geomFilter = vtk.vtkGeometryFilter()
        self.geomFilter.SetInputConnection(self.idFilter.GetOutputPort())
        self.geomFilter.Update()

    # Pick
    def pickMark(self, x, y):
        self.picker.Pick(x, y, 0, self.ren)
        pickPos = self.picker.GetPickPosition()
        if (self.picker.GetCellId() != -1):
            print("cellPicked")
            if (self.mark(pickPos)):
                    #                self.ren.AddActor(clipActor)
                    #                print("clipActor")
                self.POINT_SET.append(pickPos)
                    #                self.MARKER_SET.append(clipActor)
                self.new_marker_id += 1
                self.data.Modified()
                self.renWin.Render()

    def mark(self, pos):
        self.sphere.SetCenter(pos)

        clipEx = vtk.vtkExtractPolyDataGeometry()
        clipEx.SetInputConnection(self.geomFilter.GetOutputPort())
        clipEx.SetImplicitFunction(self.sphere)
        clipEx.ExtractInsideOn()
        clipEx.ExtractBoundaryCellsOn()
        clipEx.Update()

        clipData = vtk.vtkPolyData()
        clipData = clipEx.GetOutput()

        ids = vtk.vtkIdTypeArray()
        ids = clipData.GetCellData().GetArray("OriginalIds")

        if ids.GetNumberOfTuples() != 0:
            for i in range(0,ids.GetNumberOfTuples()):
#               print("Id", i, ids.GetValue(i))
                self.Marked.SetValue(ids.GetValue(i),1)
                self.Colors.SetComponent(ids.GetValue(i),0,0)
                self.Colors.SetComponent(ids.GetValue(i),1,255)
                self.Colors.SetComponent(ids.GetValue(i),2,0)

            #self.data.GetCellData().SetScalars(self.Colors)
            self.Colors.Modified()
            print(ids.GetNumberOfTuples(),"polygons are selected.")
            return 1
        else:
            return 0

    # Marking contour
    def MarkContour1(self,x,y,pos):
        print("MarkContour",self.MyContourWidget.GetWidgetState(), pos[0],pos[1],pos[2])

        self.data.BuildLinks()

        idList = vtk.vtkIdList()
        rep = self.MyContourWidget.GetContourRepresentation()
        interp = rep.GetLineInterpolator()
        interp.GetContourPointIds(rep, idList)

        if idList.GetNumberOfIds() >= 3:
            selectionPoints = vtk.vtkPoints()
            point = [.0, .0, .0]
            for i in range(0, idList.GetNumberOfIds()):
                self.data.GetPoint(idList.GetId(i), point)
                selectionPoints.InsertPoint(i, point)
            loop = vtk.vtkSelectPolyData()
            loop.SetInputData(self.data)
            loop.SetLoop(selectionPoints)
            loop.GenerateSelectionScalarsOn()
#            loop.GenerateUnselectedOutputOn()
#            loop.SetSelectionModeToLargestRegion()
            loop.SetClosestPoint(pos[0], pos[1], pos[2])
            loop.SetSelectionModeToClosestPointRegion()
            loop.Update()

            ptIds = vtk.vtkIdList()
            loopdata = vtk.vtkPolyData
            loopdata = loop.GetOutput()
            loopsc = vtk.vtkFloatArray()
            loopsc = loopdata.GetPointData().GetScalars()

            self.picker.Pick(x, y, 0, self.ren)
#            pickPos = self.picker.GetPickPosition()

            if self.contourMarked == 1:
                self.contourMarked = 2  # reverse
            else:
                self.contourMarked = 1

            for i in range(0, self.data.GetNumberOfPolys()):
                self.data.GetCellPoints(i, ptIds)
                if self.contourMarked == 2:
                    if loopsc.GetTuple1(ptIds.GetId(0)) < 0 and loopsc.GetTuple1(
                            ptIds.GetId(1)) < 0 and loopsc.GetTuple1(
                            ptIds.GetId(2)) < 0:
                        self.Colors.SetComponent(i, 0, 0)
                        self.Colors.SetComponent(i, 1, 0)
                        self.Colors.SetComponent(i, 2, 128)
                        self.Marked.SetValue(i, 1)
                    else:
                        self.Colors.SetComponent(i, 0, 128)
                        self.Colors.SetComponent(i, 1, 128)
                        self.Colors.SetComponent(i, 2, 128)
                        self.Marked.SetValue(i, 0)
                else:
                    if loopsc.GetTuple1(ptIds.GetId(0)) < 0 and loopsc.GetTuple1(
                            ptIds.GetId(1)) < 0 and loopsc.GetTuple1(
                            ptIds.GetId(2)) < 0:
                        self.Colors.SetComponent(i, 0, 128)
                        self.Colors.SetComponent(i, 1, 128)
                        self.Colors.SetComponent(i, 2, 128)
                        self.Marked.SetValue(i, 0)
                    else:
                        self.Colors.SetComponent(i, 0, 0)
                        self.Colors.SetComponent(i, 1, 0)
                        self.Colors.SetComponent(i, 2, 128)
                        self.Marked.SetValue(i, 1)

            self.Colors.Modified()
            self.renWin.Render()

    def MarkContour2(self, x, y, pos):
        print("MarkContour", self.MyContourWidget.GetWidgetState(), pos[0], pos[1], pos[2])

        self.data.BuildLinks()

        idList = vtk.vtkIdList()
        rep = self.MyContourWidget.GetContourRepresentation()
        interp = rep.GetLineInterpolator()
        interp.GetContourPointIds(rep, idList)

        if idList.GetNumberOfIds() >= 3:
            selectionPoints = vtk.vtkPoints()
            point = [.0, .0, .0]
            for i in range(0, idList.GetNumberOfIds()):
                self.data.GetPoint(idList.GetId(i), point)
                selectionPoints.InsertPoint(i, point)

            loop = vtk.vtkSelectPolyData()
            loop.SetInputData(self.data)
            loop.SetLoop(selectionPoints)
            loop.GenerateSelectionScalarsOn()
            loop.Update()
            loopdata = vtk.vtkPolyData
            loopdata = loop.GetOutput()

            clipper = vtk.vtkClipPolyData()
            clipper.SetInputData(loopdata)
            clipper.GenerateClippedOutputOn()
            clipper.SetValue(0.0)

            if self.contourMarked == 1:
                self.contourMarked = 2  # reverse
                clipper.InsideOutOn()
            else:
                self.contourMarked = 1
                clipper.InsideOutOff()
            clipper.Update()

            loopMapper = vtk.vtkPolyDataMapper()
            loopMapper.SetInputData(clipper.GetClippedOutput())
            loopMapper.ScalarVisibilityOff()

            if hasattr(self,'loopActor')==False:
                self.loopActor = vtk.vtkActor()
                self.loopActor.SetMapper(loopMapper)
                self.loopActor.GetProperty().SetColor(51/255, 153/255, 255/255)
                self.ren.AddActor(self.loopActor)
            else:
                loopMapper.Update()
                self.loopActor.SetMapper(loopMapper)

            #self.mapper.ScalarVisibilityOff()
            self.Colors.Modified()
            self.renWin.Render()


    def clip(self):
        if self.mode == 1:
            print ("Clipping contour")
            nMarkedPolys = 0;
            for i in range(0, self.data.GetNumberOfPolys()):
                if self.Marked.GetValue(i):
                    nMarkedPolys += 1
                    self.data.DeleteCell(i)
            self.data.RemoveDeletedCells()
            print(nMarkedPolys, "of ", self.nOrigPolys, "polygons are marked and deleted in total.")

            self.MyContourWidget.SetEnabled(0)
            self.mode = 0

        elif self.mode == 2 and len(self.POINT_SET) > 0:
            # Clipping  self.v.data using clip with self.v.POINT_SET
            nMarkedPolys = 0;
            for i in range(0, self.data.GetNumberOfPolys()):
                if self.Marked.GetValue(i):
                    nMarkedPolys += 1
                    self.data.DeleteCell(i)
            self.data.RemoveDeletedCells()
            print(nMarkedPolys, "of ", self.nOrigPolys, "polygons are marked and deleted in total.")

        print("Number of Poly:", self.data.GetNumberOfPolys())
        print("Number of Points:", self.nOrigPoints, self.data.GetNumberOfPoints())


        for i in range(0, self.data.GetNumberOfPolys()):
            self.Marked.SetValue(i, 0)
            self.Colors.SetComponent(i, 0, 128)
            self.Colors.SetComponent(i, 1, 128)
            self.Colors.SetComponent(i, 2, 128)
        self.data.GetCellData().SetScalars(self.Colors)

        if self.new_marker_id !=0:
            del self.POINT_SET[0:self.new_marker_id]
            del self.MARKER_SET[0:self.new_marker_id]
        self.new_marker_id = 0

        self.Colors.Modified()
        self.data.Modified()
        self.picker.RemoveAllLocators()
        self.locator.Update()  # still need to check
        self.picker.AddLocator(self.locator)
#        self.idFilter.Update()  # I am not sure this is needed.
#        self.geomFilter.Update()  # I am not sure this is needed.
        self.mapper.Update()
        self.renWin.Render()


    def Keypress(self, iren, event):
        key = iren.GetKeySym()
        if key == 'Escape':
            print("Esc pressed")
            # todo
        elif key == "w":
            self.Wireframe()
        elif key == "s":
            self.Surface()
#        elif key == "d":
#            print("d, dual render view")


    # Routines that translate the events into camera motions.

    # This one is associated with the left mouse button. It translates x
    # and y relative motions into camera azimuth and elevation commands.
    def Rotate(self, renderer, camera, x, y, lastX, lastY, centerX, centerY):
        camera.Azimuth(lastX-x)
        camera.Elevation(lastY-y)
        camera.OrthogonalizeViewUp()
        self.renWin.Render()


    # Pan translates x-y motion into translation of the focal point and position.
    def Pan(self, renderer, camera, x, y, lastX, lastY, centerX, centerY):
        FPoint = camera.GetFocalPoint()
        FPoint0 = FPoint[0]
        FPoint1 = FPoint[1]
        FPoint2 = FPoint[2]

        PPoint = camera.GetPosition()
        PPoint0 = PPoint[0]
        PPoint1 = PPoint[1]
        PPoint2 = PPoint[2]

        renderer.SetWorldPoint(FPoint0, FPoint1, FPoint2, 1.0)
        renderer.WorldToDisplay()
        DPoint = renderer.GetDisplayPoint()
        focalDepth = DPoint[2]

        APoint0 = centerX+(x-lastX)
        APoint1 = centerY+(y-lastY)

        renderer.SetDisplayPoint(APoint0, APoint1, focalDepth)
        renderer.DisplayToWorld()
        RPoint = renderer.GetWorldPoint()
        RPoint0 = RPoint[0]
        RPoint1 = RPoint[1]
        RPoint2 = RPoint[2]
        RPoint3 = RPoint[3]

        if RPoint3 != 0.0:
            RPoint0 = RPoint0/RPoint3
            RPoint1 = RPoint1/RPoint3
            RPoint2 = RPoint2/RPoint3

        camera.SetFocalPoint( (FPoint0-RPoint0)/2.0 + FPoint0,
                              (FPoint1-RPoint1)/2.0 + FPoint1,
                              (FPoint2-RPoint2)/2.0 + FPoint2)
        camera.SetPosition( (FPoint0-RPoint0)/2.0 + PPoint0,
                            (FPoint1-RPoint1)/2.0 + PPoint1,
                            (FPoint2-RPoint2)/2.0 + PPoint2)
        self.renWin.Render()

    # Dolly converts y-motion into a camera dolly commands.
    def Dolly(self, renderer, camera, x, y, lastX, lastY, centerX, centerY):
        dollyFactor = pow(1.02,(0.5*(y-lastY)))
        if camera.GetParallelProjection():
            parallelScale = camera.GetParallelScale()*dollyFactor
            camera.SetParallelScale(parallelScale)
        else:
            camera.Dolly(dollyFactor)
            renderer.ResetCameraClippingRange()

        self.renWin.Render()

    # Wireframe sets the representation of all actors to wireframe.
    def Wireframe(self):
        actors = self.ren.GetActors()
        actors.InitTraversal()
        actor = actors.GetNextItem()
        while actor:
            actor.GetProperty().SetRepresentationToWireframe()
            actor = actors.GetNextItem()
        self.renWin.Render()

    # Surface sets the representation of all actors to surface.
    def Surface(self):
        actors = self.ren.GetActors()
        actors.InitTraversal()
        actor = actors.GetNextItem()
        while actor:
            actor.GetProperty().SetRepresentationToSurface()
            actor = actors.GetNextItem()
        self.renWin.Render()


    def start(self):
        # Enable user interface interactor
        self.loadCamera()
        self.iren.Initialize()
        self.renWin.Render()
        self.iren.Start()

    def repair(self):
        # Select largest connected region
        cFilter = vtk.vtkPolyDataConnectivityFilter()
        cFilter.SetInputData(self.data)
        cFilter.SetExtractionModeToLargestRegion()
        cFilter.Update()

        print("Connected Polygons:", cFilter.GetOutput().GetNumberOfPolys())
        print("Connected Points:", cFilter.GetOutput().GetNumberOfPoints())

#        featureEdges = vtk.vtkFeatureEdges()
#        featureEdges.SetInputData(self.data)
#        featureEdges.BoundaryEdgesOn()
#        featureEdges.FeatureEdgesOff()
#        featureEdges.ManifoldEdgesOff()
#        featureEdges.NonManifoldEdgesOn()
#        featureEdges.ColoringOn()
#        featureEdges.Update()

#        featureMapper = vtk.vtkPolyDataMapper()
#        featureMapper.SetInputConnection(featureEdges.GetOutputPort())
#        featureActor = vtk.vtkActor()
#        featureActor.SetMapper(featureMapper)
#        self.ren.AddActor(featureActor)

        tempData = vtk.vtkPolyData()
        tempData = CyMesh.TMesh_Repair(cFilter.GetOutput(), self.l1, self.l2, self.l3)

        self.repairedData = vtk.vtkPolyData()
        self.repairedData = CyMesh.CGAL_Poly3_FillHole(tempData,0,0,0)

        print("Connected Polygons:", self.repairedData.GetNumberOfPolys())
        print("Connected Points:", self.repairedData.GetNumberOfPoints())

        del tempData

        self.data = self.repairedData
        self.data.Modified()

        print(self.nOrigPolys,self.data.GetNumberOfPolys())
        if (self.nOrigPolys < self.data.GetNumberOfPolys()):
            for i in range(0,self.nOrigPolys):
                self.Colors.SetComponent(i, 0, 128)
                self.Colors.SetComponent(i, 1, 128)
                self.Colors.SetComponent(i, 2, 128)
                self.Marked.SetValue(i,0)
            for i in range(self.nOrigPolys, self.data.GetNumberOfPolys()):
                self.Colors.InsertNextTuple3(128,128,128)
                self.Marked.InsertNextTuple1((0))
        else:
            for i in range(0,self.data.GetNumberOfPolys()):
                self.Colors.SetComponent(i, 0, 128)
                self.Colors.SetComponent(i, 1, 128)
                self.Colors.SetComponent(i, 2, 128)
                self.Marked.SetValue(i,0)
            for i in range(self.data.GetNumberOfPolys(), self.nOrigPolys):
                self.Colors.RemoveLastTuple()
                self.Marked.RemoveLastTuple()

        self.data.GetCellData().SetScalars(self.Colors)
        self.nOrigPolys = self.data.GetNumberOfPolys()
        self.nOrigPoints = self.data.GetNumberOfPoints()

        self.picker.RemoveAllLocators()
        self.locator.Update()  # still need to check
        self.picker.AddLocator(self.locator)
        self.mapper.SetInputData(self.data)
        self.actor.Render(self.ren,self.mapper)
        self.renWin.Render()

    def checkOri(self,a,b,c,rPoint):
        ax = b[0] - a[0]
        ay = b[1] - a[1]
        az = b[2] - a[2]
        bx = c[0] - a[0]
        by = c[1] - a[1]
        bz = c[2] - a[2]
        cx = rPoint[0] - a[0]
        cy = rPoint[1] - a[1]
        cz = rPoint[2] - a[2]

        return ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx)

    def checkVol(self,i,rPoint):
        ptIds = vtk.vtkIdList()
        a = [.0, .0, .0]
        b = [.0, .0, .0]
        c = [.0, .0, .0]

        # check visible
        self.data.GetCellPoints(i, ptIds)
        self.data.GetPoint(ptIds.GetId(0), a)
        self.data.GetPoint(ptIds.GetId(1), b)
        self.data.GetPoint(ptIds.GetId(2), c)
        ax = a[0] - rPoint[0]
        ay = a[1] - rPoint[1]
        az = a[2] - rPoint[2]
        bx = b[0] - rPoint[0]
        by = b[1] - rPoint[1]
        bz = b[2] - rPoint[2]
        cx = c[0] - rPoint[0]
        cy = c[1] - rPoint[1]
        cz = c[2] - rPoint[2]
        vol = ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx)
        if (vol < -0.5): return -1
        else:   return 1

        # Coloring face and adjacent faces by color

    def MarkConnectedBackFaces(self, rPoint, color):
        # Mark Connected Backface by DFS search
        self.data.BuildLinks()
        nt = self.data.GetNumberOfPolys()

        j=0
        for i in range(0,nt):
            vol = self.checkVol(i, rPoint)
            if vol<0:
                self.Marked.SetValue(i, 1)
                self.Colors.SetComponent(i, 0, color[0])
                self.Colors.SetComponent(i, 1, color[1])
                self.Colors.SetComponent(i, 2, color[2])
                j=j+1
            else:
                self.Colors.SetComponent(i, 0, 128)
                self.Colors.SetComponent(i, 1, 128)
                self.Colors.SetComponent(i, 2, 128)
                self.Marked.SetValue(i, 0)

#        print("Total face Marked:",j)

        ptIds = vtk.vtkIdList()
        cellId = vtk.vtkIdList()
        neighborCellIds = vtk.vtkIdList()

        j = 0
        start = 0
        while (start < nt):

            for i in range(start, nt):
                if self.Marked.GetValue(i) & 2 != 0:
                    i = i + 1
                    continue
                if self.Marked.GetValue(i) & 1 == 1:  # back face
                    break
                else:
                    i = i + 1

            start = i
            if (start == nt): break

            # for group j
            hEdgeList = []
            faceList = []

            # starting from face i to mark connected back faces((group j) and mark edges
            faceList.append(-1)
            iFaceNum = i
            k=0
            while (len(faceList) > 0):
                l = self.Marked.GetValue(iFaceNum)
                if l & 2 == 0:
                    self.Marked.SetValue(iFaceNum, l | 2)
                    # processing
                    self.Colors.SetComponent(iFaceNum, 0, color[0])
                    self.Colors.SetComponent(iFaceNum, 1, color[1])
                    self.Colors.SetComponent(iFaceNum, 2, color[2])
                    k=k+1
                else:
                    iFaceNum = faceList.pop()
                    if iFaceNum < 0:
                        break
                    else:
                        self.Marked.SetValue(iFaceNum, l & 3)
                        continue

                self.data.GetCellPoints(iFaceNum, ptIds)
                #            print("Redmark: ", iFaceNum, ptIds.GetId(0), ptIds.GetId(1),ptIds.GetId(2),len(faceList),self.Marked.GetValue(iFaceNum))

                self.data.GetCellEdgeNeighbors(iFaceNum, ptIds.GetId(2), ptIds.GetId(0), neighborCellIds)
                if neighborCellIds.GetNumberOfIds() == 0:
                    pass
                elif neighborCellIds.GetNumberOfIds() == 1:
                    cellId = neighborCellIds.GetId(0)
                    l = self.Marked.GetValue(cellId)
                    if self.Marked.GetValue(cellId) & 1 == 0:  # front face
                        hEdgeList.append((ptIds.GetId(0), ptIds.GetId(1)))
                    elif l & 7 == 1:
                        faceList.append(cellId)
                        self.Marked.SetValue(cellId, l | 4)
                else:
                    print("non-manifold edges!")

                self.data.GetCellEdgeNeighbors(iFaceNum, ptIds.GetId(1), ptIds.GetId(2), neighborCellIds)
                if neighborCellIds.GetNumberOfIds() == 0:
                    pass
                elif neighborCellIds.GetNumberOfIds() == 1:
                    cellId = neighborCellIds.GetId(0)
                    l = self.Marked.GetValue(cellId)
                    if self.Marked.GetValue(cellId) & 1 == 0:  # front face
                        hEdgeList.append((ptIds.GetId(0), ptIds.GetId(1)))
                    if l & 7 == 1:
                        faceList.append(cellId)
                        self.Marked.SetValue(cellId, l | 4)
                else:
                    print("non-manifold edges!")

                self.data.GetCellEdgeNeighbors(iFaceNum, ptIds.GetId(0), ptIds.GetId(1), neighborCellIds)
                if neighborCellIds.GetNumberOfIds() == 0:
                    pass
                elif neighborCellIds.GetNumberOfIds() > 1:
                    print("non-manifold edges!")
                else:
                    cellId = neighborCellIds.GetId(0)
                    if self.Marked.GetValue(cellId) & 1 == 0:  # front face
                        hEdgeList.append((ptIds.GetId(0), ptIds.GetId(1)))
                    else:
                        if self.Marked.GetValue(cellId) & 7 == 1:
                            iFaceNum = cellId
                            #                       print("Next face:(continue to back face)",iFaceNum)
                            continue

                iFaceNum = faceList.pop()
                l = self.Marked.GetValue(iFaceNum)
                self.Marked.SetValue(iFaceNum, l & 3)
                #           print("Next face:(pop)", iFaceNum)
                if iFaceNum < 0: break

            j=j+1
 #           if (len(hEdgeList)>50):
 #               print(j,start, k," faces", len(hEdgeList)," edges")

        print("Number of connected back face sets", j)

    def MarkConnectedHiddenFaces(self, color):
        # ray intesection test for finding hidden face

        # Make OBBTree locator
        tolerance = 0.00000001
        sampling = 256

        bBox = self.extrudedData.GetBounds()
        center = self.extrudedData.GetCenter()
        print(bBox, center)

        tree = vtk.vtkOBBTree()
        tree.SetDataSet(self.extrudedData)
        tree.BuildLocator()
        tree.SetTolerance(0.0000001)

        print("tree built", tree.GetLevel())

        intersectionPoints = vtk.vtkPoints()
        intersectionCells = vtk.vtkIdList()

        delta = max(bBox[1] - bBox[0], bBox[3] - bBox[2]) / sampling
        lineP0 = [.0, .0, .0]
        lineP1 = [.0, .0, .0]

        print(delta)
        startTime = time.time()
        n = 0
        for i in range(0, sampling + 1):
            for j in range(0, sampling + 1):
                # define line
                x = bBox[0] + delta * i
                y = bBox[2] + delta * j
                lineP0[0] = x
                lineP0[1] = y
                lineP0[2] = bBox[4] - delta
                lineP1[0] = x
                lineP1[1] = y
                lineP1[2] = bBox[5] + delta
                # intesect
                tree.IntersectWithLine(lineP0, lineP1, intersectionPoints, intersectionCells)
                if intersectionCells.GetNumberOfIds() > 1:
                    n = n + intersectionCells.GetNumberOfIds() - 1
                    #                    print(x,y,intersectionCells.GetNumberOfIds(),intersectionCells.GetId(1))
                    for k in range(1, intersectionCells.GetNumberOfIds()):
                        l = intersectionCells.GetId(k)
                        self.Colors.SetComponent(l, 0, color[0])
                        self.Colors.SetComponent(l, 1, color[1])
                        self.Colors.SetComponent(l, 2, color[2])

        print("occlusion test and marked", n, time.time() - startTime)

    def MarkOccludedFaces(self,rPoint1):
        # Mark Occluded Face using Depth Buffer
        winX = 1024
        winY = 1024

        nt = self.extrudedData.GetNumberOfPolys()
        bBox = self.extrudedData.GetBounds()
        center = self.extrudedData.GetCenter()

        # Make offscreen render window
        renderer = vtk.vtkRenderer()
        renderWindow = vtk.vtkRenderWindow()
        renderWindow.SetOffScreenRendering(1)
        renderWindow.SetSize(winX,winY)
        renderWindow.AddRenderer(renderer)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(self.extrudedData)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        renderer.AddActor(actor)

        xBounded = True
        # Assume Window viewport x:y=3:4(600x800)
        if (bBox[3] - bBox[2])*winX > (bBox[1] - bBox[0])*winY:  # Y side full
            ratio = (bBox[3] - bBox[2]) / 2.0
            xBounded = False
            # World coordinate x,y, image coordinate xi,yi (xi, yi < 0 -> 0)
            # xi = ((x-bBox[0])*winY/(bBox[3]-bBox[2])+(winX-(bBox[1]-bBox[0])*winY/(bBox[3]-bBox[2])/2-0.5
            # yi = (y-bBox[2])*winY/(bBox[3]-bBox[2])-0.5
        else:
            ratio = (bBox[1] - bBox[0]) / 2.0
            # World coordinate x,y, image coordinate xi,yi (xi, yi < 0 -> 0)
            # xi = (x-bBox[0])*winX/(bBox[1]-bBox[0])-0.5
            # yi = (y-bBox[2])*winX/(bBox[1]-bBox[0])+(winY-(bBox[3]-bBox[2])*winX/(bBox[1]-bBox[0])/2-0.5

        # z = (bBox[5]-bBox[4])*(maxZ-depth)/(maxZ-minZ)
        # depth = z * (minZ - maxZ)/(bBox[5]-bBox[4])+ maxZ



        renderer.GetActiveCamera().ParallelProjectionOn()
        renderer.GetActiveCamera().SetPosition(center[0], center[1], center[2] + (bBox[5] - bBox[4]))
        renderer.GetActiveCamera().SetFocalPoint(center[0], center[1], center[2])
        renderer.GetActiveCamera().SetViewUp(.0, 1.0, .0)
        renderer.GetActiveCamera().SetClippingRange(0.1, 1.6 * (bBox[5] - bBox[4]))

        renderer.GetActiveCamera().SetParallelScale(ratio)
        renderWindow.Render()

        filter = vtk.vtkWindowToImageFilter()
        filter.SetInput(renderWindow)
        filter.SetScale(1, 1)
        filter.FixBoundaryOn()
        filter.SetInputBufferTypeToZBuffer()
        filter.Update()

        depthImage = vtk.vtkImageData()
        depthImage = filter.GetOutput()
        print(depthImage.GetDimensions(), depthImage.GetNumberOfCells(), depthImage.GetScalarSize())

        depthArray = vtk.vtkFloatArray()
        depthArray = depthImage.GetPointData().GetScalars()
        npArr = vtk_to_numpy(depthArray).reshape(winX,winY)

        minZ = npArr.min()
        bArr = (npArr != 1.0)
        maxZ = npArr[bArr].max()
        print(minZ, maxZ)

        i = 0
        iBegin = 0
        iEnd = 0
        for row in npArr:
            if row.sum() < winX:
                if iBegin == 0:
                    iBegin = i
                else:
                    iEnd = i
            i = i + 1
        print(iBegin, iEnd)

        # iterate all faces
        # calculate center of face(triangle)
        # compare depth value ( if visible : green, else(occluded) : red, (back face: red, front face: orange)

        ptIds = vtk.vtkIdList()
        a = [.0, .0, .0]
        b = [.0, .0, .0]
        c = [.0, .0, .0]
        f = [.0, .0, .0]

        if xBounded:
            # World coordinate x,y, image coordinate xi,yi (xi, yi < 0 -> 0)
            # xi = (x-bBox[0])*winX/(bBox[1]-bBox[0])-0.5
            # yi = (y-bBox[2])*winX/(bBox[1]-bBox[0])+(winY-(bBox[3]-bBox[2])*winX/(bBox[1]-bBox[0])/2-0.5
            t1 = winX / (bBox[1] - bBox[0])
            t2 = (winY - (bBox[3] - bBox[2]) * winX / (bBox[1] - bBox[0]))/2.0
        else:
            # World coordinate x,y, image coordinate xi,yi (xi, yi < 0 -> 0)
            # xi = ((x-bBox[0])*winY/(bBox[3]-bBox[2])+(winX-(bBox[1]-bBox[0])*winY/(bBox[3]-bBox[2])/2-0.5
            # yi = (y-bBox[2])*winY/(bBox[3]-bBox[2])-0.5
            t1 = winY / (bBox[3] - bBox[2])
            t2 = (winX - (bBox[1] - bBox[0]) * winY / (bBox[3] - bBox[2]))/2.0

        # z = (bBox[5]-bBox[4])*(maxZ-depth)/(maxZ-minZ)
        # depth = z * (minZ - maxZ)/(bBox[5]-bBox[4])+ maxZ
        t3 = (maxZ-minZ)/(bBox[5]-bBox[4])

        j = 0
        k = 0
        k1 = 0
        k2 = 0
        k3 = 0

        for i in range(nt):
            # check visible
            self.extrudedData.GetCellPoints(i, ptIds)
            self.extrudedData.GetPoint(ptIds.GetId(0), a)
            self.extrudedData.GetPoint(ptIds.GetId(1), b)
            self.extrudedData.GetPoint(ptIds.GetId(2), c)



            det = self.checkOri(a,b,c, rPoint1)
            f = [(a[l]+b[l]+c[l])/3.0 for l in range(3)]

            if xBounded:
                # World coordinate x,y, image coordinate xi,yi (xi, yi < 0 -> 0)
                xi = (int)((f[0]-bBox[0])*t1-0.51)
                yi = (int)((f[1]-bBox[2])*t1 + t2 -0.51)
            else:
                # World coordinate x,y, image coordinate xi,yi (xi, yi < 0 -> 0)
                xi = (int)((f[0]-bBox[0])*t1 + t2 - 0.51)
                yi = (int)((f[1]-bBox[2])*t1 - 0.51)

            if xi<0: xi=0
            if yi<0: yi=0
            depth = maxZ-(f[2]-bBox[4])*t3

            epsilon = 0.005
            # need more test to set epsilon value, depends on resolution

            if (depth < npArr[yi,xi]+epsilon and depth > npArr[yi,xi]-epsilon):
#                print(f[0],f[1],f[2],xi,yi,depth, npArr[yi,xi])
                j=j+1

            if depth > npArr[yi,xi]+epsilon: #occluded (-epsilon: more, +epsilon: less occluded face than actual
                if det<0: # backface(bright pink)
                    k1+=1
                    self.Colors.SetComponent(i, 0, 255)
                    self.Colors.SetComponent(i, 1, 153)
                    self.Colors.SetComponent(i, 2, 204)
                    self.Marked.SetValue(i, 1)
                else: # occluded front face(bright orange)
                    k2+=1
                    self.Colors.SetComponent(i, 0, 255)
                    self.Colors.SetComponent(i, 1, 204)
                    self.Colors.SetComponent(i, 2, 153)
                    self.Marked.SetValue(i, 2)
            else:
                if det < 0:  # backface (missing light green)
                    k3+=1
                    self.Colors.SetComponent(i, 0, 204)
                    self.Colors.SetComponent(i, 1, 255)
                    self.Colors.SetComponent(i, 2, 153)
                    self.Marked.SetValue(i, 1)
                else: # front face(grey)
                    k+=1
                    self.Colors.SetComponent(i, 0, 128)
                    self.Colors.SetComponent(i, 1, 128)
                    self.Colors.SetComponent(i, 2, 128)
                    self.Marked.SetValue(i, 0)

        print ("Number of face with its depth value(not occluded,front face) ",j,k1,k2,k3,k)
        # clean up
        renderer.RemoveActor(actor)
        del mapper
        del actor


    # This callback function does the actual work: updates the vtkPlanes
    # implicit function.  This in turn causes the pipeline to update.
    def SelectPolygons(self, object, event):
        # object will be the boxWidget
        object.GetRepresentation().GetPlanes(self.planes)
        self.selectActor.VisibilityOn()
        self.extrudedActor.GetProperty().SetOpacity(0.75)
        self.renWin.Render()

    def notify_marker(self, index):
        self.markVisibleFace(index)
#        self.iren.Render()

    def markVisibleFace(self, idxCaller):
        if (idxCaller == 999):
            cam = self.ren.GetActiveCamera()
            fp = cam.GetFocalPoint()
            pos = cam.GetPosition()

            # Make transform, make arrow, transform data, mark occluded faces, enter box2 widget
            # push extruded button -> sweep and make solid

            cam.OrthogonalizeViewUp()
            up_vec = cam.GetViewUp()

            self.CameraPos_Set.append(pos)
            self.FocalPoint_Set.append(fp)
            self.UpVector_Set.append(up_vec)

            row = Qt.QTreeWidgetItem(self.tree_view)
            row.setText(0, str(self.Camera_id))
            self.Camera_id += 1
            row.setTextAlignment(0, QtCore.Qt.AlignLeft)
            row.setText(1, str(pos))
            row.setText(2, str(fp))
            row.setText(3, str(up_vec))

        else:
            pos = self.CameraPos_Set[idxCaller]
            fp = self.FocalPoint_Set[idxCaller]
            up_vec = self.UpVector_Set[idxCaller]
            self.ren.GetActiveCamera().SetFocalPoint(fp)
            self.ren.GetActiveCamera().SetPosition(pos)
            self.ren.GetActiveCamera().SetViewUp(up_vec)
            self.renWin.Render()


        bBox = self.data.GetBounds()
        center = self.data.GetCenter()

        # view vec
        view_vec = (fp[0] - pos[0], fp[1] - pos[1], fp[2] - pos[2])

        # magnitude of view_vec
        mag = math.sqrt(sum(view_vec[i] * view_vec[i] for i in range(len(view_vec))))

        # normalized
        self.normal_vec = [view_vec[i] / mag for i in range(len(view_vec))]

        # get center
        print("FocalPoint:", fp, "Position", pos, "View Vector:", self.normal_vec)

        normalizedX = [.0, .0, .0]
        normalizedY = [.0, .0, .0]
        normalizedZ = [.0, .0, .0]
        normalizedZ = [-self.normal_vec[i] for i in range(len(self.normal_vec))]

        Math = vtk.vtkMath()

        normalizedY[0] = up_vec[0]
        normalizedY[1] = up_vec[1]
        normalizedY[2] = up_vec[2]

        Math.Normalize(normalizedY)

        Math.Cross(normalizedY, normalizedZ, normalizedX)
        Math.Normalize(normalizedX)

        viewTran = vtk.vtkMatrix4x4()
        viewTran.Identity()
        for i in range(0,3):
            viewTran.SetElement(i, 0, normalizedX[i])
            viewTran.SetElement(i, 1, normalizedY[i])
            viewTran.SetElement(i, 2, normalizedZ[i])

#        print(viewTran)

        arrowTran = vtk.vtkTransform()
        arrowTran.Identity()
        arrowTran.Translate(center)
        arrowTran.Concatenate(viewTran)
        arrowTran.RotateY(-90)
        # arrow size
        arrowTran.Scale(20, 20, 20)

        transformPD = vtk.vtkTransformPolyDataFilter()
        transformPD.SetTransform(arrowTran)
        transformPD.SetInputConnection(self.viewArrow.GetOutputPort())
        transformPD.Update()

        if hasattr(self,'arrowActor')==False:
            self.arrowMapper = vtk.vtkPolyDataMapper()
            self.arrowMapper.SetInputData(transformPD.GetOutput())
            self.arrowActor = vtk.vtkActor()
            self.arrowActor.SetMapper(self.arrowMapper)
            self.ren.AddActor(self.arrowActor)
        else:
            self.arrowMapper.SetInputData(transformPD.GetOutput())
            self.arrowActor.SetMapper(self.arrowMapper)
            self.arrowActor.Render(self.ren, self.arrowMapper)

        # Transform data
        viewTran.Invert()
#        print(viewTran)

#        modelviewTran = vtk.vtkMatrix4x4()
#        modelviewTran = self.ren.GetActiveCamera().GetModelViewTransformMatrix()
#        print(modelviewTran)

        modelTran = vtk.vtkTransform()
        modelTran.Identity()
        modelTran.Concatenate(viewTran)
        modelTran.Translate(-center[0], -center[1], -center[2])

#        resBox1 = [.0,.0,.0]
#        resBox2 = [.0,.0,.0]
#        modelTran.TransformPoint([bBox[0], bBox[2], bBox[4]], resBox1)
#        modelTran.TransformPoint([bBox[1], bBox[3], bBox[5]], resBox2)
#        print(center)
#        print((resBox1[0]+resBox2[0])/2,(resBox1[1]+resBox2[1])/2,(resBox1[2]+resBox2[2])/2)

        transformPD2 = vtk.vtkTransformPolyDataFilter()
        transformPD2.SetTransform(modelTran)
        transformPD2.SetInputDataObject(self.data)
        transformPD2.Update()

        tempData = vtk.vtkPolyData()
        tempData = transformPD2.GetOutput()
#        print(tempData.GetBounds())
        center = tempData.GetCenter()
        newmodelTran = vtk.vtkTransform()
        newmodelTran.Identity()
        newmodelTran.Translate(-center[0], -center[1], -center[2])
        transformPD3 = vtk.vtkTransformPolyDataFilter()
        transformPD3.SetTransform(newmodelTran)
        transformPD3.SetInputDataObject(tempData)
        transformPD3.Update()

        if hasattr(self, 'ren2') == False:
            self.ren2 = vtk.vtkRenderer()
            self.renWin.AddRenderer(self.ren2)
            self.ren.SetViewport(.0, .0, .5, 1.0)
            self.ren2.SetViewport(.5, .0, 1.0, 1.0)

        if hasattr(self,'extrudedData') == False:
            self.extrudedData = vtk.vtkPolyData()
            self.extrudedData = transformPD3.GetOutput()
            extrudedMapper = vtk.vtkPolyDataMapper()
            extrudedMapper.SetInputData(self.extrudedData)
            extrudedMapper.ScalarVisibilityOn()
            self.extrudedActor = vtk.vtkActor()
            self.extrudedActor.SetMapper(extrudedMapper)

#            forProp = vtk.vtkProperty()
#            forProp.SetColor([1.0, 1.0, 1.0])
#            self.extrudedActor.SetProperty(forProp)
            self.ren2.AddActor(self.extrudedActor)
        else:
            self.extrudedData = transformPD3.GetOutput()
#            self.ren2.RemoveActor(self.extrudedActor)
            extrudedMapper = vtk.vtkPolyDataMapper()
            extrudedMapper.SetInputData(self.extrudedData)
            extrudedMapper.ScalarVisibilityOn()
            self.extrudedActor.SetMapper(extrudedMapper)

            self.extrudedData.Modified()

        self.renWin.Render()

        bBox = self.extrudedData.GetBounds()
        center = self.extrudedData.GetCenter()
        BigNumber = 1000000 * (bBox[5] - bBox[4])  # X direction
        rPoint1 = (center[0], center[1], center[2] + BigNumber)
        rPoint2 = (center[0], center[1], center[2] - BigNumber)
        print("ExtrudedData", id(self.extrudedData), bBox, center)

        # Marking color: light orange
#        color = (255,204,153)
        # Mark Occluded Faces
#        self.MarkConnectedHiddenFaces(color)
#        self.MarkConnectedBackFaces(rPoint1, color)
        beginTime=time.time()
        vUCV = vtk.vtkDoubleArray()
        vUCV = CyMesh.Pagoda_UCV(self.extrudedData, self.normal_vec[0], self.normal_vec[1], self.normal_vec[2])

        self.extrudedData.GetPointData().SetScalars(vUCV)

#        self.MarkOccludedFaces(rPoint1) # using Z-buffer
#        print("Zbuffer Occlusion Calc Time",time.time()-beginTime)
        print("Pagoda Occlusion Calc Time",time.time()-beginTime)

        pUCV = vtk.vtkDoubleArray()
        for i in range(self.extrudedData.GetNumberOfPolys()):
            ptSum = 0.0
            for j in range(3) :
                ptSum = ptSum + vUCV.GetValue(self.extrudedData.GetCell(i).GetPointId(j))
            ptSum = ptSum/3.0
            pUCV.InsertNextValue(ptSum)

#            self.Colors.SetComponent(i, 0, int(25.5*ptSum))
#            self.Colors.SetComponent(i, 1, int(25.5*ptSum))
#            self.Colors.SetComponent(i, 2, int(25.5*ptSum))
        self.extrudedData.GetCellData().SetScalars(pUCV)
#        bEdges = vtk.vtkPolyData()
#        bEdges = CyMesh.CGAL_Poly3_Sweep(self.extrudedData, self.Marked, rPoint1[0], rPoint1[1], rPoint1[2],14)
#        #self.extrudedData = CyMesh.CGAL_Poly3_Remesh(self.extrudedData,0.8)
#        print("Connected Component Calc Time",time.time()-beginTime)
#        print(bEdges.GetNumberOfPoints(),bEdges.GetNumberOfCells(),bEdges.GetNumberOfLines(),bEdges.GetNumberOfPolys())
#        bedgeMapper = vtk.vtkPolyDataMapper()
#        bedgeMapper.SetInputData(bEdges)
#        bedgeActor = vtk.vtkActor()
#        bedgeActor.SetMapper(bedgeMapper)
#        bedgeActor.GetProperty().SetColor(255, 0, 0)
#        self.ren2.AddActor(bedgeActor)

        k = 0
#        for i in range(self.extrudedData.GetNumberOfPolys()):
#            mType = self.Marked.GetValue(i) & 12288
#            if mType == 4096:  # back face : pink
#                self.Colors.SetComponent(i, 0, 255)
#                self.Colors.SetComponent(i, 1, 153)
#                self.Colors.SetComponent(i, 2, 204)
#            elif mType == 8192:  # occluded : orange
#                self.Colors.SetComponent(i, 0, 255)
#                self.Colors.SetComponent(i, 1, 204)
#                self.Colors.SetComponent(i, 2, 153)
#            else:
#                self.Colors.SetComponent(i, 0, 128)
#                self.Colors.SetComponent(i, 1, 128)
#                self.Colors.SetComponent(i, 2, 128)

        bBox = self.extrudedData.GetBounds()
        center = self.extrudedData.GetCenter()
        self.ren2.GetActiveCamera().SetFocalPoint(center[0], center[1], center[2])
        self.ren2.GetActiveCamera().SetPosition(center[0], center[1] + 3 * (bBox[3] - bBox[2]), center[2])
        self.ren2.GetActiveCamera().SetViewUp(0, 0, 1)

        self.ren2.ResetCamera()
        # fBound = [.0, .0, .0, .0, .0, .0]
        # self.ren2.ComputeVisiblePropBounds(fBound)
        # fBound[0] = bBox[0] - (bBox[1] - bBox[0]) / 2
        # fBound[1] = bBox[1] + (bBox[1] - bBox[0]) / 2
        # fBound[2] = bBox[2] - (bBox[3] - bBox[2]) / 2
        # fBound[3] = bBox[3] + (bBox[3] - bBox[2]) / 2
        # fBound[4] = bBox[4] - (bBox[5] - bBox[4]) / 2
        # fBound[5] = bBox[5] + (bBox[5] - bBox[4]) / 2
        # self.ren2.ResetCameraClippingRange(fBound)

        if hasattr(self, 'selectActor') == False:
            self.planes = vtk.vtkPlanes()
            clipper = vtk.vtkClipPolyData()
            clipper.SetInputData(self.extrudedData)
            clipper.SetClipFunction(self.planes)
            clipper.InsideOutOn()
            selectMapper = vtk.vtkPolyDataMapper()
            selectMapper.SetInputConnection(clipper.GetOutputPort())
            self.selectActor = vtk.vtkLODActor()
            self.selectActor.SetMapper(selectMapper)
            self.selectActor.GetProperty().SetColor(0, 1, 0)
            #            self.selectActor.GetProperty().SetOpacity(0.75)
            self.selectActor.VisibilityOff()
            self.selectActor.SetScale(1.01, 1.01, 1.01)
            self.ren2.AddActor(self.selectActor)
            selectMapper.ScalarVisibilityOff()
        else:
            self.selectActor.GetProperty().SetColor(0, 1, 0)
            self.selectActor.GetProperty().SetOpacity(0.75)
            self.selectActor.VisibilityOff()
            #            self.selectActor.SetScale(1.01, 1.01, 1.01)

        if hasattr(self, 'boxWidget'):
            del self.boxWidget

        boxRep = vtk.vtkBoxRepresentation()
        boxRep.SetRenderer(self.ren2)
        boxRep.SetPlaceFactor(1.05)
        boxRep.PlaceWidget(bBox)

        self.boxWidget = vtk.vtkBoxWidget2()
        self.boxWidget.SetInteractor(self.iren)
        self.boxWidget.SetRepresentation(boxRep)
        self.boxWidget.TranslationEnabledOff()
        self.boxWidget.ScalingEnabledOff()
        self.boxWidget.RotationEnabledOff()
        self.boxWidget.AddObserver("EndInteractionEvent", self.SelectPolygons)

        self.mode = 4
        self.boxWidget.On()

        self.Colors.Modified()
        self.data.Modified()
        self.extrudedData.Modified()
        extrudedMapper.SetInputData(self.extrudedData)

        # for Coloring
        colorSeries = vtk.vtkColorSeries()
        color = vtk.vtkColor3ub()
        lut = vtk.vtkColorTransferFunction()
        lut.SetColorSpaceToHSV()
        colorSeries.SetColorScheme(15)

        nColors = colorSeries.GetNumberOfColors()

        for i in range(nColors):
            color = colorSeries.GetColor(i)
            d1 = (color[0]/255.0)
            d2 = (color[1]/255.0)
            d3 = (color[2]/255.0)
            t = 255.0*i/(nColors-1)
            lut.AddRGBPoint(t,d1,d2,d3)

        extrudedMapper.SetLookupTable(lut)
        extrudedMapper.SetScalarRange(0.0,10.0)

        self.extrudedActor.SetMapper(extrudedMapper)
        self.renWin.Render()


    def extrudeModel(self):

        # Cleanup view
        if hasattr(self,'arrowActor'):
            self.ren.RemoveActor(self.arrowActor)
            del self.arrowActor
        if hasattr(self,"extrudedActor"):
            self.ren2.RemoveActor(self.extrudedActor)
            del self.extrudedActor
        if hasattr(self, 'selectActor'):
            self.ren2.RemoveActor(self.selectActor)
            del self.selectActor
        if hasattr(self,"boxWidget"):
            del self.boxWidget
        if hasattr(self,"ren2"):
            self.renWin.RemoveRenderer(self.ren2)
            del self.ren2
        # Adjust viewport
            self.ren.SetViewport(.0, .0, 1.0, 1.0)

        # Restore to single Renderer
        self.mode = 5
        self.renWin.Render()

        # Make sweep
        if hasattr(self,'extrudeData'):
            self.data = CyMesh.Pagoda_RemoveUC(self.extrudeData, self.normal_vec[0], self.normal_vec[1], self.normal_vec[2])

        # Assign to self.data
#        self.data = self.extrudedData
        self.data.Modified()
        print(self.nOrigPolys, self.data.GetNumberOfPolys())
        if (self.nOrigPolys < self.data.GetNumberOfPolys()):
            for i in range(0, self.nOrigPolys):
                self.Colors.SetComponent(i, 0, 128)
                self.Colors.SetComponent(i, 1, 128)
                self.Colors.SetComponent(i, 2, 128)
                self.Marked.SetValue(i, 0)
            for i in range(self.nOrigPolys, self.data.GetNumberOfPolys()):
                self.Colors.InsertNextTuple3(128, 128, 128)
                self.Marked.InsertNextTuple1((0))
        else:
            for i in range(0, self.data.GetNumberOfPolys()):
                self.Colors.SetComponent(i, 0, 128)
                self.Colors.SetComponent(i, 1, 128)
                self.Colors.SetComponent(i, 2, 128)
                self.Marked.SetValue(i, 0)
            for i in range(self.data.GetNumberOfPolys(), self.nOrigPolys):
                self.Colors.RemoveLastTuple()
                self.Marked.RemoveLastTuple()

        self.data.GetCellData().SetScalars(self.Colors)
        self.nOrigPolys = self.data.GetNumberOfPolys()
        self.nOrigPoints = self.data.GetNumberOfPoints()

        self.picker.RemoveAllLocators()
        self.locator.Update()  # still need to check
        self.picker.AddLocator(self.locator)

        bBox = self.data.GetBounds()
        center = self.data.GetCenter()
        self.ren.GetActiveCamera().SetFocalPoint(center[0], center[1], center[2])
        self.ren.GetActiveCamera().SetPosition(center[0], center[1] + 3 * (bBox[3] - bBox[2]), center[2])
        self.ren.GetActiveCamera().SetViewUp(0, 0, 1)

        #self.ren.ResetCamera()
        fBound = [.0, .0, .0, .0, .0, .0]
        self.ren.ComputeVisiblePropBounds(fBound)
        fBound[0] = bBox[0] - (bBox[1] - bBox[0]) / 2
        fBound[1] = bBox[1] + (bBox[1] - bBox[0]) / 2
        fBound[2] = bBox[2] - (bBox[3] - bBox[2]) / 2
        fBound[3] = bBox[3] + (bBox[3] - bBox[2]) / 2
        fBound[4] = bBox[4] - (bBox[5] - bBox[4]) / 2
        fBound[5] = bBox[5] + (bBox[5] - bBox[4]) / 2
        self.ren.ResetCameraClippingRange(fBound)

        self.mapper.SetInputData(self.data)
        self.renWin.Render()


    def contour(self):
        self.contourPick()

    def offsetModel2(self):
        self.MyContourWidget.SetEnabled(0)

        self.data.BuildLinks()
        idList = vtk.vtkIdList()
        rep = self.MyContourWidget.GetContourRepresentation()
        interp = rep.GetLineInterpolator()
        interp.GetContourPointIds(rep, idList)
        # Assert idList.GetNumberOfIds()>3        if idList.GetNumberOfIds() < 3:
        selectionPoints = vtk.vtkPoints()
        offsetPoints = vtk.vtkPoints()

        point = [.0, .0, .0]
        ppoint = [.0, .0, .0]
        j = 0
        self.data.GetPoint(idList.GetId(0), ppoint)
        selectionPoints.InsertPoint(0, ppoint)
        print(0, ppoint)
        for i in range(1, idList.GetNumberOfIds()):
            self.data.GetPoint(idList.GetId(i), point)
            if ppoint[0] != point[0] or ppoint[1] != point[1] or ppoint[2] != point[2]:
                print(i, point)
                selectionPoints.InsertPoint(j, point)
                j += 1
            ppoint[0] = point[0]
            ppoint[1] = point[1]
            ppoint[2] = point[2]
        print(idList.GetNumberOfIds(), selectionPoints.GetNumberOfPoints())

        # get lower surface model
        loop = vtk.vtkSelectPolyData()
        loop.SetInputData(self.data)
        loop.SetLoop(selectionPoints)
        loop.GenerateSelectionScalarsOn()
        loop.Update()
        loopdata = vtk.vtkPolyData
        loopdata = loop.GetOutput()

        clipper = vtk.vtkClipPolyData()
        clipper.SetInputData(loopdata)
        clipper.GenerateClippedOutputOn()
        clipper.SetValue(0.0)

        if self.contourMarked == 1:
            clipper.InsideOutOff()
        else:
            clipper.InsideOutOn()
        clipper.Update()

        tempdata1 = vtk.vtkPolyData()
        tempdata2 = vtk.vtkPolyData()

        cleaner = vtk.vtkCleanPolyData()
        cleaner.AddInputConnection(clipper.GetClippedOutputPort())
        cleaner.PointMergingOff()
        cleaner.ConvertLinesToPointsOff()
        cleaner.ConvertPolysToLinesOff()
        cleaner.ConvertStripsToPolysOff()
        cleaner.Update()

        reverser = vtk.vtkReverseSense()
        reverser.SetInputConnection(cleaner.GetOutputPort())
        reverser.ReverseCellsOn()
        reverser.Update()

        tempdata1 = reverser.GetOutput()

        stlWriter = vtk.vtkSTLWriter()
        stlWriter.SetFileName("bottom.stl")
        stlWriter.SetInputData(tempdata1)
        stlWriter.SetFileTypeToBinary()
        stlWriter.Write()

        # Make offset using MeshThickening
        self.offsetedModel = vtk.vtkPolyData()
        self.offsetedModel = MeshWorks.MeshWorks_Thicken(tempdata1,512,4.0)

        # Cleaning and Repair
        #stlWriter.SetFileName("offset.stl")
        #stlWriter.SetInputData(self.offsetedModel)
        #stlWriter.SetFileTypeToBinary()
        #stlWriter.Write()

    def offsetModel(self):
        # stop contourWidget
        #Assert hasattr(self,"MyContourWidget")    if hasattr(self,"MyContourWidget")==False:
        self.MyContourWidget.SetEnabled(0)

        self.data.BuildLinks()
        idList = vtk.vtkIdList()
        rep = self.MyContourWidget.GetContourRepresentation()
        interp = rep.GetLineInterpolator()
        interp.GetContourPointIds(rep, idList)
        #Assert idList.GetNumberOfIds()>3        if idList.GetNumberOfIds() < 3:
        selectionPoints = vtk.vtkPoints()
        offsetPoints = vtk.vtkPoints()

        point  = [.0, .0, .0]
        ppoint = [.0, .0, .0]
        j=0
        self.data.GetPoint(idList.GetId(0), ppoint)
        selectionPoints.InsertPoint(0, ppoint)
        print(0,ppoint)
        for i in range(1, idList.GetNumberOfIds()):
            self.data.GetPoint(idList.GetId(i), point)
            if ppoint[0] != point[0] or ppoint[1] != point[1] or ppoint[2] != point[2]:
                print(i, point)
                selectionPoints.InsertPoint(j, point)
                j+=1
            ppoint[0] = point[0]
            ppoint[1] = point[1]
            ppoint[2] = point[2]
        print (idList.GetNumberOfIds(),selectionPoints.GetNumberOfPoints())

        # get lower surface model
        loop = vtk.vtkSelectPolyData()
        loop.SetInputData(self.data)
        loop.SetLoop(selectionPoints)
        loop.GenerateSelectionScalarsOn()
        loop.Update()
        loopdata = vtk.vtkPolyData
        loopdata = loop.GetOutput()

        clipper = vtk.vtkClipPolyData()
        clipper.SetInputData(loopdata)
        clipper.GenerateClippedOutputOn()
        clipper.SetValue(0.0)

        if self.contourMarked == 1:
            clipper.InsideOutOff()
        else:
            clipper.InsideOutOn()
        clipper.Update()

        tempdata1 = vtk.vtkPolyData()
        tempdata2 = vtk.vtkPolyData()
        tempdata3 = vtk.vtkPolyData()
        tempdata4 = vtk.vtkPolyData()

        cleaner = vtk.vtkCleanPolyData()
        cleaner.AddInputConnection(clipper.GetClippedOutputPort())
        cleaner.PointMergingOff()
        cleaner.ConvertLinesToPointsOff()
        cleaner.ConvertPolysToLinesOff()
        cleaner.ConvertStripsToPolysOff()
        cleaner.Update()

        reverser = vtk.vtkReverseSense()
        reverser.SetInputConnection(cleaner.GetOutputPort())
        reverser.ReverseCellsOn()
        reverser.Update()

        tempdata1 = reverser.GetOutput()

        stlWriter = vtk.vtkSTLWriter()
        stlWriter.SetFileName("bottom.stl")
        stlWriter.SetInputData(tempdata1)
        stlWriter.SetFileTypeToBinary()
        stlWriter.Write()

        # Make offset 1, Make offset 2
        glutInit(sys.argv)
        glutInitDisplayMode(GLUT_DEPTH | GLUT_RGBA | GLUT_ALPHA | GLUT_DOUBLE | GLUT_STENCIL)
        glutInitWindowSize(400, 200);
        glutInitWindowPosition(self.width, 800);
        winid = glutCreateWindow(b"VTKGLUT Example")

        # Using QOpenGLWindow
        #        glWindow = GLWindow()
        #        glWindow.makeCurrent();
        #        glWindow.initializeGL()
        #        glWindow.paintGL()

        # Using PyGame
        #        video_flags = OPENGL | DOUBLEBUF
        #        pygame.init()
        #        pygame.display.set_mode((640, 480))

        self.offsetedModel = vtk.vtkPolyData()

        tempdata2 = CyOffset.LDNI_Offset(self.data)
        #        pygame.quit()
        #        glutSwapBuffers()
        glutHideWindow()
        glutDestroyWindow(winid)
        #        del glWindow
        self.renWin.MakeCurrent()

        if (tempdata2):
            start = time.time()
            tempdata3 = CyMesh.TMesh_Repair(tempdata2, 1, 1, 1)
            print("Repair Time:", time.time() - start)
            start = time.time()

            #            self.offsetedModel = CyMesh.CGAL_Poly3_Simplify(tempdata2,0.25)
            #           High quality but slow
            #            decimate = vtk.vtkDecimatePro()
            decimate = vtk.vtkQuadricDecimation()
            decimate.SetInputData(tempdata3)
            decimate.SetTargetReduction(.25)
            decimate.Update()
            print("Decimation Time:", time.time() - start)
            start = time.time()

            offsetPoints = CyMesh.CGAL_Poly3_MakeSeparator(decimate.GetOutput(), selectionPoints, 0.5, 0.5)

            # loop and clipper...
            loop2 = vtk.vtkSelectPolyData()
            loop2.SetInputData(decimate.GetOutput())
            loop2.SetLoop(offsetPoints)
            loop2.GenerateSelectionScalarsOn()
            loop2.Update()
            loopdata = loop2.GetOutput()
            clipper2 = vtk.vtkClipPolyData()
            clipper2.SetInputData(loopdata)
            clipper2.GenerateClippedOutputOn()
            clipper2.SetValue(0.0)
            clipper2.Update()

            cleaner2 = vtk.vtkCleanPolyData()
            cleaner2.SetInputConnection(clipper2.GetClippedOutputPort())
            cleaner2.PointMergingOff()
            cleaner2.ConvertLinesToPointsOff()
            cleaner2.ConvertPolysToLinesOff()
            cleaner2.ConvertStripsToPolysOff()
            cleaner2.Update()
            tempdata4 = cleaner2.GetOutput()


#            stlWriter.SetFileName("top.stl")
#            stlWriter.SetInputData(tempdata4)
#            stlWriter.SetFileTypeToBinary()
#            stlWriter.Write()


            # Locator
            # locator = vtk.vtkPointLocator()
            locator = vtk.vtkPointLocator()
            locator.SetDataSet(tempdata1)
            locator.BuildLocator()
            j1 = locator.FindClosestPoint(selectionPoints.GetPoint(0))

            locator.SetDataSet(tempdata4)
            locator.BuildLocator()

            # in fact, should find closest border vertex
            j2 = locator.FindClosestPoint(offsetPoints.GetPoint(0))

            self.offsetedModel = CyMesh.CGAL_Poly3_BorderEdges(tempdata1, tempdata4, j1, j2)

#            appender = vtk.vtkAppendPolyData()
#            appender.AddInputData(tempdata1)
#            appender.AddInputData(tempdata4)
#            appender.Update()
#            self.offsetedModel = appender.GetOutput()

            print(tempdata1.GetNumberOfPolys(),tempdata4.GetNumberOfPolys(),self.offsetedModel.GetNumberOfPolys())

#            stlWriter = vtk.vtkSTLWriter()
#            stlWriter.SetFileName("offset.stl")
#            stlWriter.SetInputData(self.offsetedModel)
#            stlWriter.SetFileTypeToBinary()
#            stlWriter.Write()

        # remove scalar in self.data
            for i in range(0,self.nOrigPolys):
                self.Colors.SetComponent(i, 0, 128)
                self.Colors.SetComponent(i, 1, 128)
                self.Colors.SetComponent(i, 2, 128)
                self.Marked.SetValue(i,0)
            self.data.Modified()

        # two actors with mappers scalar visibility off
            offsetMapper = vtk.vtkPolyDataMapper()
            offsetMapper.SetInputData(self.offsetedModel)
            offsetMapper.ScalarVisibilityOff()
            self.offsetActor = vtk.vtkActor()
            self.offsetActor.SetMapper(offsetMapper)
            self.offsetActor.GetProperty().SetColor(0/255, 255/255, 0/255)
            self.offsetActor.GetProperty().SetOpacity(0.75)
            self.ren.AddActor(self.offsetActor)
        else:
            print("Offset was not calculated well")

        self.actor.Render(self.ren, self.mapper)
        self.renWin.Render()


class MainWindow(QtWidgets.QWidget):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        
        # selected point idx
        self.idx_selected_point = -1
        
        self.isRemoving = False
        
        self.filename = ""

        rec = QApplication.desktop().screenGeometry()
        width = rec.width();
        height = rec.height();
        print("Screen Resolution ",width,height)

        # mainwindow: 400x800, view window: 4:3
        if width>2400:
            width=min(2400,int(4*height/3)+400)
        print("View Window",width,height)
        self.width = width
        self.height = height

        self.move(width-400,0)
        self.resize(400, 800)

        btn1 = QPushButton('Load STL File', clicked=self.on_click_stl_load)
        btn2 = QPushButton('Select Surface for Trim', clicked=self.on_click_trim_stl)
        btn3 = QPushButton('Mark Surface for Trim', clicked=self.on_click_clean_stl)
        btn4 = QPushButton('Trim Surface', clicked=self.on_click_remove)
        btn5 = QPushButton('Repair Model', clicked=self.on_click_repair)
        btn6 = QPushButton('Check Undercut', clicked=self.on_click_viewvector)
        btn7 = QPushButton('Blockout Undercut', clicked=self.on_click_extrude)
        btn8 = QPushButton('Select Offset Region', clicked=self.on_click_contour)
        btn9 = QPushButton('Offset Model', clicked=self.on_click_offset)
        btn10 = QPushButton('Undo', clicked=self.on_click_undo)
        btn0 = QPushButton('Save All', clicked=self.on_click_saveall)

        # for current view vector
        # self.text_box = QTextEdit()

        layout1 = QVBoxLayout()

        # for radius of marking sphere
        self.text_box2 = QLineEdit()
        self.text_box2.setText("2")
        radius = QLabel()
        radius.setText("Marking Sphere Radius:")

        clean_widget = QtWidgets.QWidget()
        layout2 = QHBoxLayout()
        layout2.addWidget(btn3)
        layout2.addWidget(radius)
        layout2.addWidget(self.text_box2)
        clean_widget.setLayout(layout2)

        repair_widget = QtWidgets.QWidget()
        layout3 = QHBoxLayout()
        self.b1 = QCheckBox("Non-manifold")
        self.b2 = QCheckBox("Patching Hole")
        self.b3 = QCheckBox("Degeneracy/Intersection")
        self.b1.setChecked(True)
        self.b2.setChecked(True)
        self.b3.setChecked(True)
        self.b1.stateChanged.connect(lambda: self.btnstate(self.b1))
        self.b2.stateChanged.connect(lambda: self.btnstate(self.b2))
        self.b3.stateChanged.connect(lambda: self.btnstate(self.b3))
        layout3.addWidget(self.b1)
        layout3.addWidget(self.b2)
        layout3.addWidget(self.b3)
        layout3.addWidget(btn5)
        repair_widget.setLayout(layout3)

        self.tree_view = QtWidgets.QTreeWidget()
        header = Qt.QTreeWidgetItem()
        header.setText(0, r'Id')
        header.setText(1, r'CameraPos')
        header.setText(2, r'FocalPoint')
        header.setText(3, r'UpVector')
        self.tree_view.setHeaderItem(header)
        self.tree_view.header().resizeSection(0, 50)  # ?
        self.tree_view.itemClicked.connect(self.treeitem_clicked)

        undercut_widget = QtWidgets.QWidget()
        layout4 = QHBoxLayout()
        self.text_box3 = QLineEdit()
        self.text_box3.setText("0.0")
        allowUndercut = QLabel()
        allowUndercut.setText("Allow Undercuts up to")
        layout4 = QHBoxLayout()
        layout4.addWidget(btn6)
        layout4.addWidget(allowUndercut)
        layout4.addWidget(self.text_box3)
        undercut_widget.setLayout(layout4)

        extrude_widget = QtWidgets.QWidget()
        layout5 = QHBoxLayout()
        self.text_box4 = QLineEdit()
        self.text_box4.setText("0.0")
        offsetAngle = QLabel()
        offsetAngle.setText("OffsetAngle:")
        layout5 = QHBoxLayout()
        layout5.addWidget(btn7)
        layout5.addWidget(offsetAngle)
        layout5.addWidget(self.text_box4)
        extrude_widget.setLayout(layout5)

        offset_widget = QtWidgets.QWidget()
        layout6 = QHBoxLayout()
        self.text_box5 = QLineEdit()
        self.text_box5.setText("0.0")
        thickness = QLabel()
        thickness.setText("Thickness:")
        self.text_box6 = QLineEdit()
        self.text_box6.setText("0.0")
        clearing = QLabel()
        clearing.setText("Clearing Space:")
        layout6 = QHBoxLayout()
        layout6.addWidget(btn9)
        layout6.addWidget(thickness)
        layout6.addWidget(self.text_box5)
        layout6.addWidget(clearing)
        layout6.addWidget(self.text_box6)
        offset_widget.setLayout(layout6)

        layout1.addWidget(btn1)
        layout1.addWidget(btn2)
        layout1.addWidget(clean_widget)
        layout1.addWidget(btn4)
        layout1.addWidget(btn5)
        layout1.addWidget(repair_widget)
        layout1.addWidget(undercut_widget)
        layout1.addWidget(self.tree_view)
        layout1.addWidget(extrude_widget)
        layout1.addWidget(btn8)
        layout1.addWidget(offset_widget)
        layout1.addWidget(btn10)
        layout1.addWidget(btn0)

        self.setLayout(layout1)
        self.text_box2.textChanged.connect(self.textChanged)
        self.show()

        # load stl
        self.open_stl_file(width,height)


    def btnstate(self,b):
        if hasattr(self, 'v'):
            if b.text() == "Non-manifold":
                if b.isChecked() == True:
                    self.v.l1 = 1
                else:
                    self.v.l1 = 0
            elif b.text() == "Patching Hole":
                if b.isChecked() == True:
                    self.v.l2 = 1
                else:
                    self.v.l2 = 0
            elif b.text() == "Degeneracy/Intersection":
                if b.isChecked() == True:
                    self.v.l3 = 1
                else:
                    self.v.l3 = 0

    def textChanged(self,string):
        if hasattr(self, 'v'):
            radius = float(string)
            self.v.sphereRadius = radius
            self.v.sphere.SetRadius(radius)

    def open_stl_file(self,width,height):
        qfile_dlg = Qt.QFileDialog()
        qfile_dlg.setFileMode(Qt.QFileDialog.AnyFile)
        if qfile_dlg.exec_():
            filenames = qfile_dlg.selectedFiles()
            self.filename = filenames[0]

            if self.filename[len(self.filename) - 3:len(self.filename)] != 'stl':
                Qt.QMessageBox.information(QtWidgets.QWidget(), 'msg', "is not stl file!")
                return

            print("Open file", self.filename)
            self.v = Viewer(self.filename,width,height)
            self.v.set_point_tree(self.tree_view)
            self.v.start()

    @QtCore.pyqtSlot()        
    def on_click_stl_load(self):
        """
        Start Cleanup
        """
        # clean up
        self.idx_selected_point = -1
        if hasattr(self,'text_box'):
            self.text_box.clear()
        self.filename = ""
        
        if hasattr(self, 'v'):
            self.v.renWin.Finalize()
            self.v.iren.TerminateApp()
            self.v.clean()
            del self.v

            if hasattr(self,'v'): print("Still exist")
            else: print("Viewer looks cleaned")

        self.open_stl_file(self.width,self.height)


    @QtCore.pyqtSlot()
    def on_click_trim_stl(self):
        """
        Trim by Contour Widget
        """
        if hasattr(self, 'v'):
            self.v.mode = 1
            self.v.contourPick()
        else:
            Qt.QMessageBox.information(QtWidgets.QWidget(), 'msg', ".stl file isn't loaded!")


    @QtCore.pyqtSlot()
    def on_click_clean_stl(self):
        if hasattr(self, 'v'):
            self.v.mode = 2
            self.v.startMark()
        else:
            Qt.QMessageBox.information(QtWidgets.QWidget(), 'msg', ".stl file isn't loaded!")


    @QtCore.pyqtSlot()
    def on_click_remove(self):
        """
        Remove Selected Region
        """
        if hasattr(self, 'v'):
            self.v.clip()
            self.v.mode = 2
        else:
            Qt.QMessageBox.information(QtWidgets.QWidget(), 'msg', ".stl file isn't loaded!")


    @QtCore.pyqtSlot()
    def on_click_repair(self):
        """
        Trim by Contour Widget
        """
        if hasattr(self, 'v'):
            self.v.mode = 3
            self.v.repair()
        else:
            Qt.QMessageBox.information(QtWidgets.QWidget(), 'msg', ".stl file isn't loaded!")

    @QtCore.pyqtSlot()
    def on_click_viewvector(self):
        """
        Convex View Vector
        """
        if hasattr(self, 'v'):
            self.v.markVisibleFace(999)
        else:
            Qt.QMessageBox.information(QtWidgets.QWidget(), 'msg', ".stl file isn't loaded!")


    def treeitem_clicked(self, column):
        if (self.v.mode == 4):
            self.idx_selected_camera = self.tree_view.indexOfTopLevelItem(column)
            self.v.notify_marker(self.idx_selected_camera)
            print(column,self.idx_selected_camera)

    @QtCore.pyqtSlot()
    def on_click_extrude(self):
        """
        Convex View Vector
        """
        if hasattr(self, 'v'):
            self.v.mode = 5

            self.v.extrudeModel()
        else:
            Qt.QMessageBox.information(QtWidgets.QWidget(), 'msg', ".stl file isn't loaded!")


    @QtCore.pyqtSlot()
    def on_click_contour(self):
        """
        Select Contour
        """
        if hasattr(self, 'v'):
            self.v.mode = 6
            self.v.contour()
        else:
            Qt.QMessageBox.information(QtWidgets.QWidget(), 'msg', ".stl file isn't loaded!")

        
    @QtCore.pyqtSlot()    
    def on_click_offset(self):
        """
        calculate offset 
        """
        if hasattr(self, 'v'):
            self.v.offsetModel2()
            self.v.mode = 7
        else:
            Qt.QMessageBox.information(QtWidgets.QWidget(), 'msg', ".stl file isn't loaded!")

    @QtCore.pyqtSlot()
    def on_click_undo(self):
        """
        undo
        """
        if hasattr(self, 'v'):
            self.v.mode = 6
            self.v.get_view_vector()
        else:
            Qt.QMessageBox.information(QtWidgets.QWidget(), 'msg', ".stl file isn't loaded!")

    @QtCore.pyqtSlot()
    def on_click_saveall(self):
        """
        calculate offset
        """
        if hasattr(self, 'v'):
            destDir = Qt.QFileDialog.getExistingDirectory(None, 'Open directory for saving', '',
                                                          Qt.QFileDialog.ShowDirsOnly)
            self.v.save_all(destDir)
        else:
            Qt.QMessageBox.information(QtWidgets.QWidget(), 'msg', ".stl file isn't loaded!")

    def closeEvent(self, e):
        print('Close')
        if hasattr(self, 'v'):
            self.v.renWin.Finalize()
            self.v.iren.TerminateApp()
            self.v.clean()
            del self.v
        sys.exit(0)

    def treeitem_clicked(self, column):
        self.idx_selected_point = self.tree_view.indexOfTopLevelItem(column)
        self.v.notify_marker(self.idx_selected_point)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = MainWindow()
            
    sys.exit(app.exec())
