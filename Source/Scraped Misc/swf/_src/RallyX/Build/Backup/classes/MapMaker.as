package classes {
	
	import flash.display.MovieClip;
	import flash.display.Sprite;
	import flash.events.Event;
	import flash.events.KeyboardEvent;
	import flash.events.MouseEvent;
	import classes.screens.game.LevelCell;
	import classes.screens.game.SidewalkCell;
	import classes.screens.game.RoadCell;
	import com.greensock.events.LoaderEvent;
	import com.greensock.loading.XMLLoader;
	
	public class MapMaker extends MovieClip{

		// Constants
		private const UP_ARROW:int = 87;
		private const DOWN_ARROW:int = 83;
		private const LEFT_ARROW:int = 65;
		private const RIGHT_ARROW:int = 68;
		private const SPACE:int = 32;
		private const STOP:int = 81;
		
		private const SPEEDX:Number = 5;
		private const SPEEDY:Number = 5;
		
		private var _map:Vector.<Vector.<Sprite>>;
		private var _mapMatrix:Vector.<Vector.<Boolean>>;
		private var _mapHolder:Sprite;
		private var _eastDir:Boolean;
		private var _northDir:Boolean;
		private var _speedX:Number;
		private var _speedY:Number;
		
		private var _mapLoader:XMLLoader;

		public function MapMaker() {
			_eastDir = false;
			_northDir = false;
			this.addEventListener(Event.ADDED_TO_STAGE, onInit);
		}
		
		
		// Private Methods
		private function onInit(e:Event):void{
			_mapLoader = new XMLLoader("xml/map0.xml", {onInit:onXMLLoaded, onIOError:onXMLLoadError});
			_mapLoader.load();
		}
		
		private function onXMLLoaded(e:LoaderEvent):void{		
			var _currMap:XML = XML(_mapLoader.content);
			_mapHolder = new Sprite();
			_mapMatrix = new Vector.<Vector.<Boolean>>();
			_map = new Vector.<Vector.<Sprite>>();
			
			var _numRows:int = int(_currMap.@rows);
			var _numCols:int = int(_currMap.@cols);
			var _numRanges:int;
			var _startCell:int;
			var _endCell:int;
			var _cellClass:Class;
			var _cell:LevelCell;
			var _value:Boolean;
			
			for (var i:int = 0; i<_numRows; i++){
				_mapMatrix[i] = new Vector.<Boolean>();
				for (var j:int=0; j<_numCols; j++){
					_mapMatrix[i][j] = false;
				}
			}
			
			for (i=0; i<_numRows; i++){
				trace ("i: "+i);
				if (_currMap.row[i].range!= undefined){
					_numRanges = _currMap.row[i].range.length();
					for (var r:int=0; r<_numRanges; r++){
						_startCell = int(_currMap.row[i].range[r].@startCell);
						_endCell = int(_currMap.row[i].range[r].@endCell);
						_value = (_currMap.row[i].range[r] == "true")?true:false;
						for (j=_startCell-1; j<_endCell; j++){
							_mapMatrix[i][j] = _value;
						}
					}
				}
			}
			
			for (i=0; i<_mapMatrix.length; i++){
				_map[i] = new Vector.<Sprite>();
				for (j=0; j<_mapMatrix[i].length; j++){
					_cellClass = (_mapMatrix[i][j]==true ?  RoadCell:SidewalkCell);
					_cell = new _cellClass();
					_cell.init((i+1)+", "+(j+1), i, j);
					_cell.y = 0 + i*50;
					_cell.x = 0 + j*50;
					_cell.addEventListener(MouseEvent.CLICK, onCellClick);
					_map[i][j] = _cell;
					_mapHolder.addChild (_cell);
				}
			}
			
			_mapHolder.cacheAsBitmap
			addChild (_mapHolder);
			
			this.removeEventListener(Event.ADDED_TO_STAGE, onInit);
			this.stage.addEventListener(KeyboardEvent.KEY_DOWN, onKeyPress);
			this.stage.addEventListener(Event.ENTER_FRAME, onFrameEnter);
		}
		
		private function onCellClick(e:MouseEvent):void{
			var _refCell:LevelCell = LevelCell(e.target);
			var _newCell:LevelCell;
			var _refIndex:int;
			
			_refIndex = _mapHolder.getChildIndex(_refCell);
			_mapHolder.removeChild(_refCell);
			_refCell.removeEventListener(MouseEvent.CLICK, onCellClick);

			if (_refCell.type){
				_newCell = new SidewalkCell();
			}else{
				_newCell = new RoadCell();
			}
			_newCell.init(_refCell.id, _refCell.r, _refCell.c);
			_newCell.x = _refCell.x;
			_newCell.y = _refCell.y;
			_newCell.addEventListener(MouseEvent.CLICK, onCellClick);
			_map[_refCell.r][_refCell.c] = _newCell;
			_mapMatrix[_refCell.r][_refCell.c] = _newCell.type;
			_mapHolder.addChildAt(_newCell, _refIndex);
			_refCell = null;
		}
		
		private function onKeyPress(e:KeyboardEvent):void{
			if (e.keyCode == LEFT_ARROW){
				_eastDir = false;
				_speedX = SPEEDX;
				_speedY = 0;
			}else if (e.keyCode == RIGHT_ARROW){
				_eastDir = true;
				_speedX = -1*SPEEDX;
				_speedY = 0;
			}else if (e.keyCode == DOWN_ARROW){
				_northDir = false;
				_speedY = -1*SPEEDY;
				_speedX = 0;
			}else if (e.keyCode == UP_ARROW){
				_northDir = true;
				_speedY = SPEEDY;
				_speedX = 0;
			}else if (e.keyCode == SPACE){
				printXML();
			}else if (e.keyCode == STOP){
				_speedX = 0;
				_speedY = 0;
			}
		}
		
		private function onFrameEnter(e:Event):void{
			_mapHolder.x += _speedX;
			_mapHolder.y += _speedY;
			if (_speedX < 0){
				if (_mapHolder.x < (600-_mapHolder.width )){
					_mapHolder.x =  (600-_mapHolder.width );
				}
			}else{
				if (_mapHolder.x > 0){
					_mapHolder.x =  0;
				}
			}
			
			if (_speedY < 0){
				if (_mapHolder.y < (450-_mapHolder.height )){
					_mapHolder.y =  (450-_mapHolder.height );
				}
			}else{
				if (_mapHolder.y > 0){
					_mapHolder.y =  0;
				}
			}
		}
		
		private function printXML():void{
			var _xml:XML = new XML("<map rows='"+(_mapMatrix.length)+"' cols='"+(_mapMatrix[0].length)+"'></map>");
			var _row:XML;
			var _rows:int = _mapMatrix.length;
			var _range:XML;
			for (var i:int=0; i<_rows; i++){
				var _currRange:int=0;
				var _startPoint:int=1;
				var _endPoint:int=1;
				var _found:Boolean = false;
				_row = new XML("<row id='"+(i+1)+"'></row>");
				for (var j:int=0; j<_mapMatrix[i].length; j++){
					if (_mapMatrix[i][j] == true){
						_currRange++;
					}else{
						if (_currRange > 0){
							_endPoint = _startPoint + _currRange-1;
							_range = new XML("<range startCell='"+_startPoint+"' endCell='"+_endPoint+"'>"+true+"</range>");
							_row.appendChild(_range);
							_currRange = 0;
							_startPoint= 2+_endPoint;
						}else{
							_startPoint++;
						}
					}
				}
				if (_currRange > 0){
					_range = new XML("<range startCell='"+_startPoint+"' endCell='"+(_currRange+_startPoint-1)+"'>"+true+"</range>");
					_row.appendChild(_range);
					_currRange = 0;
				}
				_xml.appendChild(_row);
			}
			trace (_xml);
		}
		
		private function onXMLLoadError(e:LoaderEvent):void{
			trace (e.text);
		}

	}// Class
}// Package