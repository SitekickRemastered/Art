package classes.screens.game {
	
	import flash.display.Sprite;
	import classes.control.GlobalControl;
	import classes.control.GameControl;
	import classes.events.GameEvent;
	import classes.screens.game.Hero;
	import flash.display.MovieClip;
	import com.greensock.TweenMax;
	
	public class Background extends Sprite{
		
		// Constants
		private const KEY_VARIANCE:int = 70;
		private const KEY_VARIANCE_RAND:int = 20;
		
		// Private Properties
		private var _currMap:XML;
		private var _keyList:Vector.<MovieClip>;
		private var _keyCells:Vector.<LevelCell>;
		private var _empList:Vector.<MovieClip>;
		private var _refHero:Hero;
		private var _enemyList:Vector.<Zomkick>;
		private var _refHud:Hud;
		
		private var _mapMatrix:Vector.<Vector.<Boolean>>;
		private var _cellMatrix:Vector.<Vector.<LevelCell>>;
		private var _mapHolder:MovieClip;
		private var _map:MovieClip;
		
		private var _mapPrevX:Number;
		private var _mapPrevY:Number;
		private var _startC:int;
		private var _startR:int;
		private var _secureR:int;
		private var _secureC:int;
		private var _keyCount:int;
		
		// Constructor
		public function Background() {
			_cellMatrix = new Vector.<Vector.<LevelCell>>();
			_enemyList = new Vector.<Zomkick>();
			_empList = new Vector.<MovieClip>();
			_keyCount = 0;
		}
		
		// Public Methods
		public function init(_mapLevel:XML):void{
			_currMap = _mapLevel;
			_mapHolder = new MovieClip();
			_mapMatrix = new Vector.<Vector.<Boolean>>();
			_cellMatrix = new Vector.<Vector.<LevelCell>>();
			
			var _numRows:int = int(_currMap.@rows);
			var _numCols:int = int(_currMap.@cols);
			var _numRanges:int;
			var _startCell:int;
			var _endCell:int;
			var _cell:LevelCell;
			var _value:Boolean;
			
			_secureR = int(_currMap.meta.secure_zone.@r);
			_secureC = int(_currMap.meta.secure_zone.@c);
			
			for (var i:int = 0; i<_numRows; i++){
				_mapMatrix[i] = new Vector.<Boolean>();
				for (var j:int=0; j<_numCols; j++){
					_mapMatrix[i][j] = false;
				}
			}
			
			for (i=0; i<_numRows; i++){
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
			
			for (i=0; i<_mapMatrix.length; i++){
				_cellMatrix[i] = new Vector.<LevelCell>();
				for (j=0; j<_mapMatrix[i].length; j++){
					_cell = (_mapMatrix[i][j]==true ?  (new RoadCell()):(new SidewalkCell()));
					_cell.init((i+1)+", "+(j+1), i+1, j+1);
					_cell.y = 0 + i*GameControl.CELL_WIDTH;
					_cell.x = 0 + j*GameControl.CELL_HEIGHT;
					_cellMatrix[i][j] = _cell;
				}
			}
			
			_mapMatrix = null;
			
			_map = new Map1();
			_map.secureZone.gotoAndStop("Closed");
			_mapHolder.addChild(_map);
			addChild (_mapHolder);
			
			if (_refHero != null){
				_refHero.setZeroPoint(_refHero.x - 25, _refHero.y - 25);
				_refHero.setCell(_cellMatrix[_startR-1][_startC-1]);
				_mapHolder.x = _refHero.x - GameControl.CELL_WIDTH/2 - (GameControl.CELL_WIDTH*(_startC-1));
				_mapHolder.y = _refHero.y - GameControl.CELL_HEIGHT/2 - (GameControl.CELL_HEIGHT*(_startR-1));
			}
			
			generateKeys();
			
			if (_refHud != null){
				_refHud.registerElements(_refHero, _keyCells, _enemyList, _secureR, _secureC); 
			}
						
			_mapPrevX = _mapHolder.x;
			_mapPrevY = _mapHolder.y;
			
			dispatchEvent(new GameEvent(GameEvent.BG_BUILT));
		}
		
		public function resetLifeVariables():void{
			_refHero.setCell(_cellMatrix[_startR-1][_startC-1]);
			_mapHolder.x = _refHero.x - GameControl.CELL_WIDTH/2 - (GameControl.CELL_WIDTH*(_startC-1));
			_mapHolder.y = _refHero.y - GameControl.CELL_HEIGHT/2 - (GameControl.CELL_HEIGHT*(_startR-1));
		}
		
		public function checkChangeDirection(_refShiftX:int, _refShiftY:int):Boolean{
			return (checkCell(_refHero.r+_refShiftY, _refHero.c+_refShiftX));
		}
		
		public function setHero(_rHero:Hero, _rBasePosR:int, _rBasePosC:int):void{
			_refHero = _rHero;
			_refHero.addEventListener(GameEvent.GOT_KEY, onHeroGotKey);
			_refHero.addEventListener(GameEvent.SET_EMP, onHeroEmp);
			_startC = _rBasePosC;
			_startR = _rBasePosR;	
		}
		
		public function setHud(_rHud:Hud):void{
			_refHud = _rHud;
			_refHud.addEventListener(GameEvent.LIFE_UP, onLifeUp);
		}
		
		
		public function addEnemy(_refEnemy:Zomkick, _rBasePosR:int, _rBasePosC:int):void{
			_enemyList[_enemyList.length] = _refEnemy;
			_refEnemy.x = _refHero.x + ((_rBasePosC-_startC)*GameControl.CELL_WIDTH) - GameControl.CELL_WIDTH/2;
			_refEnemy.y = _refHero.y + ((_rBasePosR-_startR)*GameControl.CELL_HEIGHT)- GameControl.CELL_HEIGHT/2;	
		}
		
		public function checkHeroSecure(_r:int, _c:int):Boolean{
			if (_keyCount == GameControl.TOTAL_KEYS){
				if ((_r == _secureR) && (_c == _secureC || _c-1 == _secureC)){
					return(true);
				}
			}
			return (false);
		}
		
		public function updatePosition(_refX:Number, _refY:Number){
			updateBasedOnHeroPosition(_refX, _refY);
			_refHud.updateMap(_keyCount);
		}
		
		
		
		// Internal Public Methods
		public function keyDone(_refKey:MovieClip):void{
			_refKey.visible = false;
		}
		
		// Private Methods
		private function updateBasedOnHeroPosition(_refX:Number, _refY:Number):void{
			// track previous map position for enemy movements
			_mapPrevX = _mapHolder.x;
			_mapPrevY = _mapHolder.y;

			var _roomAvail:Number;
			if (_refX != 0){
				if (_refX < 0){
					if (checkCell(_refHero.r, _refHero.c+1)){
						_mapHolder.x += _refX;
						_refHero.setNextCell(_cellMatrix[_refHero.r-1][_refHero.c], _mapHolder.x, _mapHolder.y);
					}else {
						// check for and move into extra room in cell
						_roomAvail = _mapHolder.x - _refHero.getCurrCellX();
						if (_roomAvail + _refX > 0){
							_mapHolder.x += _refX;
							if (_refHero.c < _cellMatrix[0].length){
								_refHero.setNextCell(_cellMatrix[_refHero.r-1][_refHero.c], _mapHolder.x, _mapHolder.y);
							}else{
								_refHero.setNextCell(_cellMatrix[_refHero.r-1][_refHero.c-1], _mapHolder.x, _mapHolder.y);
							}
						}else{
							_mapHolder.x = _refHero.getCurrCellX();// making sure you are not inside the next cell
							dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
						}
					}
				}else{
					if(checkCell(_refHero.r, _refHero.c-1)){
						_mapHolder.x += _refX;
						_refHero.setNextCell(_cellMatrix[_refHero.r-1][_refHero.c-2], _mapHolder.x, _mapHolder.y);
					}else {
						// check for and move into extra room in cell
						_roomAvail = _mapHolder.x - _refHero.getCurrCellX();
						if (_roomAvail+_refX < 0){
							_mapHolder.x += _refX;
							if (_refHero.c-2 >= 0){
								_refHero.setNextCell(_cellMatrix[_refHero.r-1][_refHero.c-2], _mapHolder.x, _mapHolder.y);
							}else{
								_refHero.setNextCell(_cellMatrix[_refHero.r-1][_refHero.c-1], _mapHolder.x, _mapHolder.y);
							}
						}else{
							_mapHolder.x = _refHero.getCurrCellX();// making sure you are not inside the next cell
							dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
						}
					}
				}
			}else if (_refY != 0){
				if (_refY < 0){
					if (checkCell(_refHero.r+1, _refHero.c)){
						_mapHolder.y += _refY;
						_refHero.setNextCell(_cellMatrix[_refHero.r][_refHero.c-1], _mapHolder.x, _mapHolder.y);
					}else {
						// check for and move into extra room in cell
						_roomAvail = _mapHolder.y - _refHero.getCurrCellY();
						if (_roomAvail + _refY > 0){
							_mapHolder.y += _refY;
							if (_refHero.r < _cellMatrix.length){
								_refHero.setNextCell(_cellMatrix[_refHero.r][_refHero.c-1], _mapHolder.x, _mapHolder.y);
							}else{
								_refHero.setNextCell(_cellMatrix[_refHero.r-1][_refHero.c-1], _mapHolder.x, _mapHolder.y);
							}
						}else{
							_mapHolder.y = _refHero.getCurrCellY();// making sure you are not inside the next cell
							dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
						}
					}
				}else{
					if(checkCell(_refHero.r-1, _refHero.c)){
						_mapHolder.y += _refY;
						_refHero.setNextCell(_cellMatrix[_refHero.r-2][_refHero.c-1], _mapHolder.x, _mapHolder.y);
					}else {
						// check for and move into extra room in cell
						_roomAvail = _mapHolder.y - _refHero.getCurrCellY();
						if (_roomAvail+_refY < 0){
							_mapHolder.y += _refY;
							if (_refHero.r-2 >= 0){
								_refHero.setNextCell(_cellMatrix[_refHero.r-2][_refHero.c-1], _mapHolder.x, _mapHolder.y);
							}else{
								_refHero.setNextCell(_cellMatrix[_refHero.r-1][_refHero.c-1], _mapHolder.x, _mapHolder.y);
							}
						}else{
							_mapHolder.y = _refHero.getCurrCellY();// making sure you are not inside the next cell
							dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
						}
					}
				}
			}
			//trace (_mapHolder.x+", "+_mapHolder.y);
		}
		
				
		private function checkCell(_r:int, _c:int):Boolean {
			if ((_r-1 < _cellMatrix.length) && (_r-1>-1)){
				if ((_c-1 < _cellMatrix[0].length) && (_c-1>-1)){
					return (_cellMatrix[_r-1][_c-1].type);
				}
			}
			return (false);
		}
		
		private function generateKeys():void{
			var _keysGenerated:int = 0;
			_keyList = new Vector.<MovieClip>();
			_keyCells = new Vector.<LevelCell>();
			var _cellCount = Math.floor(Math.random()*KEY_VARIANCE_RAND) + KEY_VARIANCE;
			for (var i:int = 0; i<_cellMatrix.length; i++){
				for (var j:int = 0; j<_cellMatrix[i].length; j++){
					if ((_cellMatrix[i][j].type) && (_cellMatrix[i][j] != _refHero.getCurrCell())){
						_cellCount--;
						if (_cellCount == 0){
							var _key:MovieClip = new Key();
							_key.x = _cellMatrix[i][j].x;
							_key.y = _cellMatrix[i][j].y;
							_key.refParent = this;
							_mapHolder.addChild(_key);
							_keyList.push(_key);
							_cellMatrix[i][j].setKey(true, _key);
							_keyCells.push(_cellMatrix[i][j]);
							_keysGenerated++;
							if (_keysGenerated == GameControl.TOTAL_KEYS){
								return;
							}
							_cellCount = Math.floor(Math.random()*KEY_VARIANCE_RAND) + KEY_VARIANCE;
						}
					}
				}
			}
		}
		
		private function onHeroGotKey(e:GameEvent):void{
			var _currCell = RoadCell(e._data);
			var _key:MovieClip = _currCell.getKey();
			if (_key!=null){
				_key.scoreClip.scoreTxt.text = GameControl.BASE_KEY_VALUE * GameControl._multiplier;
				_key.gotoAndPlay("Pickup");
				GameControl._score += GameControl.BASE_KEY_VALUE * GameControl._multiplier;
				_refHud.updateScore();
				GameControl._multiplier++;
			}
			_currCell.setKey(false);
			_keyCount++;
			if (_keyCount == GameControl.TOTAL_KEYS){
				_map.secureZone.gotoAndStop("Open");
			}
		}
		
		private function onHeroEmp(e:GameEvent):void{
			var _currCell:RoadCell = RoadCell(e._data);
			var _emp:MovieClip = new EMP();
			_emp.x = _currCell.x;
			_emp.y = _currCell.y;
			_emp.refCell = _currCell;
			_currCell.applyEmp(_emp);
			_mapHolder.addChild(_emp);
			_emp.gotoAndPlay(1);
			_empList.push(_emp);
			TweenMax.to(_emp, GameControl.EMP_TIME, {onComplete:onEmpDone, onCompleteParams:[_emp]});
		}

		private function onEmpDone(_refEmp:MovieClip):void{
			for (var i:int = 0; i<_empList.length; i++){
				if (_empList[i] == _refEmp){
					_empList.splice(i, 1);
				}
			}
			if (_refEmp.refCell.getEmp() == _refEmp){
				_refEmp.refCell.clearEmp();
			}
			_refEmp.refCell = null;
			_mapHolder.removeChild(_refEmp);
			_refEmp.stop();
		}
		
		private function onLifeUp(e:GameEvent):void{
			trace ("caught life up");
		}

	}// Class
}// Package