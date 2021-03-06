import random
import math
import pygame

import libtcodpy as tcod

import ECS
from Util import TileTypes

import Cheats
import GameData

class Map:
    def __init__( self, width, height, tiles, screen, fovUpdater ):
        self.width = width
        self.height = height
        self.surface = None
        self.visibleSurface = None

        self.renderDirty = True
        self.tcodMapDirty = True
        self.atlas = tiles
        self.target = screen

        self.fovUpdater = fovUpdater

        self.pathEnd = None

    def I( self, x, y ):
        return x + y * self.width

    def get( self, x, y ):
        return self._buffer[ self.I( x, y ) ]

    def findPath( self, start, end ):
        def point( p ):
            return ( int( math.floor( p.x ) ), int( math.floor( p.y ) ) )

        start = point( start )
        end = point( end )

        if self.pathEnd != end:
            self.pathEnd = end

            self.dijkstra = tcod.dijkstra_new( self.tcodMap, 1.41421356237 )
            tcod.dijkstra_compute( self.dijkstra, end[0], end[1] )

        if not tcod.dijkstra_path_set( self.dijkstra, start[0], start[1] ):
            return None

        ret = []
        while not tcod.dijkstra_is_empty( self.dijkstra ):
            x, y = tcod.dijkstra_path_walk( self.dijkstra )
            ret.append( ( x, y ) )

        return ret


    def isPassable( self, x, y ):
        if self.tcodMapDirty:
            self.updateTcod()

        return tcod.map_is_walkable( self.tcodMap, x, y ) or Cheats.ViewAll

    def isVisible( self, x, y ):
        if self.tcodMapDirty:
            self.updateTcod()

        return tcod.map_is_in_fov( self.tcodMap, x, y ) or Cheats.ViewAll


    def set( self, x, y, val ):
        self._buffer[ self.I( x, y ) ] = val

        self.renderDirty = True

        if not self.tcodMapDirty:
            tile = TileTypes[ val ]
            tcod.map_set_properties( self.tcodMap, x, y, tile.viewThrough, tile.passable )

    def makeMap( self, getVal, preIterInit, postInit ):
        I = lambda x, y: x + y * self.width

        #_buffer = bytearray( [ ( 1 if random.random() > 0.5 else 0 ) for _ in range( self.width * self.height ) ] )
        halfHeight = int( self.height / 2 )
        halfWidth = int( self.width / 2 )
        _buffer = bytearray( [ getVal( x, y ) for y in range( -halfHeight, halfHeight ) for x in range( -halfWidth, halfWidth ) ])
        _backBuffer = bytearray( self.width * self.height )

        preIterInit( self, I, _buffer )

        for iterI in range( 2 ):
            offsets = (
                    I(-1,-1), I(-1,0), I(-1,1),
                    I(0,1),
                    I(1,1), I(1,0), I(1,-1),
                    I(0,-1) )

            for x in range( 1, self.width - 1 ):
                for y in range( 1, self.height - 1 ):
                    i = I( x, y )

                    count = (
                        _buffer[ i + offsets[0] ] +
                        _buffer[ i + offsets[1] ] +
                        _buffer[ i + offsets[2] ] +
                        _buffer[ i + offsets[3] ] +
                        _buffer[ i + offsets[4] ] +
                        _buffer[ i + offsets[5] ] +
                        _buffer[ i + offsets[6] ] +
                        _buffer[ i + offsets[7] ] )

                    ### Maze gen
                    #if count == 3:
                    #    _backBuffer[ i ] = 1
                    #elif count == 0 or count > 5:
                    #    _backBuffer[ i ] = 0
                    #else:
                    #    _backBuffer[ i ] = _buffer[ i ]

                    if count in ( 6, 7, 8 ):
                        _backBuffer[ i ] = 1
                    elif count in ( 1, 2, 3 ):
                        _backBuffer[ i ] = 0
                    else:
                        _backBuffer[ i ] = _buffer[ i ]


            preIterInit( self, I, _backBuffer )

            temp = _buffer
            _buffer = _backBuffer
            _backBuffer = temp

        postInit( self, I, _buffer )
        self._buffer = _buffer

    def preRender( self, camX, camY ):
        tileCount = (
                ( int( self.target.get_width() / self.atlas.tileSize[0] ) + 2 ),
                ( int( self.target.get_height() / self.atlas.tileSize[1] ) + 2 ) )

        if self.surface is None:
            self.surface = pygame.Surface( (
                 tileCount[0] * self.atlas.tileSize[0],
                 tileCount[1] * self.atlas.tileSize[1]
                 ) )

            self.visibleSurface = pygame.Surface( (
                 tileCount[0] * self.atlas.tileSize[0],
                 tileCount[1] * self.atlas.tileSize[1]
                 ) )

            self.surface.set_alpha( 100 )
            self.visibleSurface.set_colorkey( ( 254, 0, 254 ) )

        self.surface.fill( ( 0, 0, 0 ) )
        self.visibleSurface.fill( ( 254, 0, 254 ) )

        for y in range( tileCount[1] ):
            _y = y * self.atlas.tileSize[1]

            if y + camY >= self.height:
                continue

            for x in range( tileCount[0] ):
                if x + camX >= self.width:
                    continue

                i = self.I( x + camX, y + camY )
                val = self._buffer[ i ]
                _x = x * self.atlas.tileSize[1]

                visible = tcod.map_is_in_fov( self.tcodMap, x + camX, y + camY ) or Cheats.ViewAll
                tileType = TileTypes[ val ]

                if visible and tileType.transparent:
                    GameData.MainAtlas.render( GameData.FloorAtlasIndex, self.visibleSurface, _x, _y )

                tileType.render( ( self.visibleSurface if visible else self.surface ), _x, _y, x + camX, y + camY )

    def updateTcod( self ):
        self.tcodMap = tcod.map_new( self.width, self.height )
        self.tcodMapDirty = False

        i = 0
        for y in range( 0, self.height ):
            for x in range( 0, self.width ):
                tile = TileTypes[ self._buffer[ i ] ]
                tcod.map_set_properties( self.tcodMap, x, y, tile.viewThrough, tile.passable )

                i+= 1

    def render( self, x, y ):
        renderX = int( x / self.atlas.tileSize[0] )
        renderY = int( y / self.atlas.tileSize[1] )

        if self.tcodMapDirty:
            self.updateTcod()

        if ( self.renderDirty or renderX != self.lastRenderX or renderY != self.lastRenderY ):
            self.renderDirty = False
            self.lastRenderX = renderX
            self.lastRenderY = renderY

            self.fovUpdater.updateFov( self.tcodMap )

            self.preRender( renderX, renderY )

        rect = pygame.Rect( x % self.atlas.tileSize[0], y % self.atlas.tileSize[1], self.target.get_width(), self.target.get_height() )
        self.target.blit( self.surface.subsurface( rect ), ( 0, 0 ) )
        self.target.blit( GameData.Fog, ( 0, 0 ) )
        self.target.blit( self.visibleSurface.subsurface( rect ), ( 0, 0 ) )
