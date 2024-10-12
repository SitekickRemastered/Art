package classes.game {
	
	import flash.display.MovieClip;
	import classes.game.Hero;
	import classes.game.ZoneKey;
	import classes.game.Zomkick;
	import classes.game.EMP;
	import classes.control.GameControl;
	import classes.control.GlobalControl;
	import classes.events.GameEvent;
	import com.greensock.TweenMax;
	import flash.display.Sprite;
	import flash.media.Sound;
	
	public class Background extends MovieClip {
		
		// Constants
		private const KEY_VARIANCE:int = 70;
		private const KEY_VARIANCE_RAND:int = 20;

		// Private Properties
		private var _map:MovieClip;
		private var _secureZone:MovieClip;
		private var _cellMatrix:Vector.<Vector.<LevelCell>>;
		private var _keyList:Vector.<ZoneKey>;
		private var _enemyList:Vector.<Zomkick>;
		private var _empList:Vector.<EMP>;
		
		private var _refHero:Hero;
		private var _secureR:int;
		private var _secureC:int;
		private var _prevX:Number;
		private var _prevY:Number;
		private var _wasHorizontal:Boolean;
		private var _secureOpen:Boolean;
		private var _heroStartR:int;
		private var _heroStartC:int;
		private var _empSnd:Sound;
		
		
		// Constructor
		public function Background() {
			stop();	
			_empSnd = new SmokeSND();
			_keyList = new Vector.<ZoneKey>();
			_cellMatrix = new Vector.<Vector.<LevelCell>>();
			_secureZone = new SecureZone();
			_empList = new Vector.<EMP>();
			_wasHorizontal = true;
			_secureOpen = false;
		}
		
		// Public Methods 
		public function init(_rHero:Hero):void{
			cleanUp();
			_keyList = new Vector.<ZoneKey>();
			_cellMatrix = new Vector.<Vector.<LevelCell>>();
			_secureZone = new SecureZone();
			_empList = new Vector.<EMP>();
			_enemyList = new Vector.<Zomkick>();
			_wasHorizontal = true;
			_secureOpen = false;
			
			var _mapXML:XML = GlobalControl._maps[GameControl._gameLevel-1];			
			
			generateMap(_mapXML);

			_heroStartR = int(_mapXML.init.startCell.@r);
			_heroStartC = int(_mapXML.init.startCell.@c);
			
			_refHero = _rHero;
			_refHero.addEventListener(GameEvent.GOT_KEY, onKeyPickup);
			_refHero.addEventListener(GameEvent.SET_EMP, onSetEmp);
			_refHero.setCell(_cellMatrix[_heroStartR-1][_heroStartC-1]);
			_refHero.setNextCell(_cellMatrix[_heroStartR-1][_heroStartC-1]);
			
			_secureZone.gotoAndStop("Closed");
			_secureR = int(_mapXML.init.secure_zone.@r);
			_secureC = int(_mapXML.init.secure_zone.@c);
			_secureZone.x = GameControl.CELL_WIDTH*(_secureC-1);
			_secureZone.y = GameControl.CELL_HEIGHT*(_secureR-1);

			this.x = _refHero.x -(GameControl.CELL_WIDTH/2) - (GameControl.CELL_WIDTH*(_heroStartC-1));
			this.y = _refHero.y -(GameControl.CELL_HEIGHT/2) - (GameControl.CELL_HEIGHT*(_heroStartR-1));
			
			
			addChild (_map);
			addChild (_secureZone);
			generateKeys();
			generateEnemies();
		}
		
		public function cleanUp():void{
			// clean up hero
			if (_refHero != null){
				if (_refHero.hasEventListener(GameEvent.GOT_KEY)){
					_refHero.removeEventListener(GameEvent.GOT_KEY, onKeyPickup);
					_refHero.removeEventListener(GameEvent.SET_EMP, onSetEmp);
				}
			}
			
			// reset secure zone
			_secureZone.gotoAndStop("Closed");
			
			// destroy keys
			if (_keyList != null){
				while(_keyList.length!=0){
					_keyList[0].destroy();
					_keyList[0].removeEventListener(GameEvent.KEY_ANIM_DONE, onKeyAnimDone);
					removeChild (_keyList[0]);
					_keyList[0] = null;
					_keyList.splice(0, 1);
				}
				_keyList = null;
			}
			
			//destroy map
			if (_map != null){
				removeChild (_map);
				_map.stop();
				_map = null;
			}
			
			// destroy map info
			if (_cellMatrix != null){
				for (var i:int=0; i<_cellMatrix.length; i++){
					for (var j:int = 0; j<_cellMatrix[i].length; j++){
						_cellMatrix[i][j].destroy();
						_cellMatrix[i][j] = null;
					}
				}
				_cellMatrix = null;
			}
			
			// destroy emp
			clearEmp();
			
			// destroy enemies
			if (_enemyList != null){
				while (_enemyList.length!=0){
					removeChild (_enemyList[0]);
					_enemyList[0].destroy();
					_enemyList.splice(0,1);
				}
				_enemyList = null;
			}
		}
		
		public function resetLevel():void{
			clearEmp();
			_empList = new Vector.<EMP>();
			_refHero.setEmp(false);
			_refHero.setCell(_cellMatrix[_heroStartR-1][_heroStartC-1]);
			_refHero.setNextCell(_cellMatrix[_heroStartR-1][_heroStartC-1]);
			this.x = _refHero.x -(GameControl.CELL_WIDTH/2) - (GameControl.CELL_WIDTH*(_heroStartC-1));
			this.y = _refHero.y -(GameControl.CELL_HEIGHT/2) - (GameControl.CELL_HEIGHT*(_heroStartR-1));
			for (var i:int=0;i<_enemyList.length; i++){
				_enemyList[i].resetPosition();
			}
		}
		
		public function playCrash():void{
			for (var i:int=0; i<_enemyList.length; i++){
				_enemyList[i].confused();
			}
		}
		
		public function getCell(_r:int, _c:int):LevelCell{
			return (_cellMatrix[_r-1][_c-1]);
		}
		
		public function updatePositions(_dispX:Number, _dispY:Number, _direction):int{
			var _retDir:int = updateHeroPosition(_dispX, _dispY, _direction);
			//updateEnemyPositions(_dispX, _dispY);
			trace ("returning: "+_retDir);
			return (_retDir);
		}
		
		public function getKeyList():Vector.<ZoneKey> {
			return (_keyList);
		}
		
		public function getEnemyList():Vector.<Zomkick>{
			return (_enemyList);
		}
		
		public function checkNorth():Boolean{
			if (_secureOpen){
				if ((_refHero.r-1 == _secureR+1) && ((_refHero.c == _secureC) || (_refHero.c == _secureC+1))){
					dispatchEvent(new GameEvent(GameEvent.WIN_LEVEL));
				}
			}
			return (checkCell(_refHero.r-1, _refHero.c));
		}
		public function checkSouth():Boolean{
			return (checkCell(_refHero.r+1, _refHero.c));
		}
		public function checkEast():Boolean{
			return (checkCell(_refHero.r, _refHero.c+1));
		}
		public function checkWest():Boolean{
			return (checkCell(_refHero.r, _refHero.c-1));
		}
		
		// Private Methods
		private function clearEmp():void{
			if (_empList != null){
				while (_empList.length!= 0){
					if (_empList[0]!= null){
						TweenMax.killTweensOf(_empList[0]);
						_empList[0].destroy();
						removeChild (_empList[0]);
						_empList[0] = null;
					}
					_empList.splice(0, 1);
				}
				_empList = null;
			}
		}
		
		private function checkCell(_r:int, _c:int):Boolean {
			if ((_r-1 < _cellMatrix.length) && (_r-1>-1)){
				if ((_c-1 < _cellMatrix[0].length) && (_c-1>-1)){
					return (_cellMatrix[_r-1][_c-1].type);
				}
			}
			return (false);
		}

		private function generateMap(_mapXML:XML):void{
			var _numRows:int = int(_mapXML.@rows);
			var _numCols:int = int(_mapXML.@cols);
			var _numRanges:int;
			var _startCell:int;
			var _endCell:int;
			var _cell:LevelCell;
			var _value:Boolean;
			
			_cellMatrix = new Vector.<Vector.<LevelCell>>();
			for (var i:int = 0; i<_numRows; i++){
				_cellMatrix[i] = new Vector.<LevelCell>();
				for (var j:int=0; j<_numCols; j++){
					_cell = new LevelCell();
					_cell.init((i+1)+", "+(j+1), i+1, j+1);
					_cell.y = i*GameControl.CELL_WIDTH;
					_cell.x = j*GameControl.CELL_HEIGHT;
					_cellMatrix[i][j] = _cell;
				}
			}
			for (i=0; i<_numRows; i++){
				_numRanges = _mapXML.row[i].range.length();
				for (var r:int=0; r<_numRanges; r++){
					_startCell = int(_mapXML.row[i].range[r].@startCell);
					_endCell = int(_mapXML.row[i].range[r].@endCell);
					_value = (_mapXML.row[i].range[r] == "true")?true:false;
					for (j=_startCell-1; j<_endCell; j++){
						_cellMatrix[i][j].type = _value;
					}
				}
			}
			switch (GameControl._gameLevel){
				case 1:
					_map = new Map1();
					break;
				case 2:
					_map = new Map2();
					break;
				case 3:
				default:
					_map = new Map3();
					break;
			}
			_map.cacheAsBitmap = true;
		}
		
		private function generateKeys():void{
			var _keysGenerated:int = 0;
			var _key:ZoneKey;
			_keyList = new Vector.<ZoneKey>();
			var _cellCount = Math.floor(Math.random()*KEY_VARIANCE_RAND) + KEY_VARIANCE;
			for (var i:int = 0; i<_cellMatrix.length; i++){
				for (var j:int = 0; j<_cellMatrix[i].length; j++){
					if ((_cellMatrix[i][j].type) && (_cellMatrix[i][j] != _refHero.getCell())){
						_cellCount--;
						if (_cellCount == 0){
							_key = new ZoneKey();
							_key.addEventListener(GameEvent.KEY_ANIM_DONE, onKeyAnimDone);
							_key.x = _cellMatrix[i][j].x;
							_key.y = _cellMatrix[i][j].y;
							_key.setCell(_cellMatrix[i][j]);
							_keyList.push(_key);
							_cellMatrix[i][j].setKey(true, _key);
							_keysGenerated++;
							addChild (_key);
							if (_keysGenerated == GameControl.TOTAL_KEYS){
								return;
							}
							_cellCount = Math.floor(Math.random()*KEY_VARIANCE_RAND) + KEY_VARIANCE;
						}
					}
				}
			}
		}
		
		private function generateEnemies():void{
			var _enemyCount:int = GameControl.BASE_ENEMY_COUNT+ GameControl.BASE_ENEMY_LEVEL_INC*GameControl._gameLevel;
			for (var i:int = 0; i<_enemyCount; i++){
				_enemyList[i] = new Zomkick(_secureR, _secureC);
				var _possCell:LevelCell = _cellMatrix[_keyList[i].r-1][_keyList[i].c-1];
				if (checkCell(_possCell.r-3, _possCell.c)){
					_possCell = _cellMatrix[_possCell.r-4][_possCell.c-1];
				}else if (checkCell(_possCell.r+3, _possCell.c)){
					_possCell = _cellMatrix[_possCell.r+2][_possCell.c-1];
				}else if (checkCell(_possCell.r, _possCell.c-3)){
					_possCell = _cellMatrix[_possCell.r-1][_possCell.c-4];
				}else {
					_possCell = _cellMatrix[_possCell.r-1][_possCell.c+2];
				}
				_enemyList[i].setMatrix(_cellMatrix);
				_enemyList[i].setCell(_possCell);
				_enemyList[i].registerHero(_refHero);
				addChild (_enemyList[i]);
				_enemyList[0].setCell(_cellMatrix[7][14]);
			}
		}
		
		private function updateHeroPosition(_dispX:Number, _dispY:Number, _direction:int):int{
			var _roomAvail:Number;
			if (_dispX < 0){
				if (_direction == GameEngine.RIGHT_ARROW || _direction == -1){
					if (checkCell(_refHero.r, _refHero.c+1)){
						_refHero.setNextCell(_cellMatrix[_refHero.r-1][_refHero.c]);
						this.x+=_dispX;
						_refHero.goEast(this.x);
					}else{
						_roomAvail =-1*(_refHero.x-this.x-GameControl.CELL_WIDTH/2  -_refHero.getNextCell().x);
						if (_roomAvail == 0){
							dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
						}else if (_roomAvail+_dispX >= 0){
							this.x+=_dispX;
							_refHero.goEast(this.x);
							_roomAvail+=_dispX;
							if (_roomAvail < 4){
								this.x -= _roomAvail;
								_refHero.goEast(this.x);
								_roomAvail = 0;
							}
							if (_roomAvail == 0){
								return (_direction);
							}
						}else {
							this.x -= _roomAvail;
							return (_direction);
						}
					}
				}else if (_direction == GameEngine.LEFT_ARROW){
					if (checkCell(_refHero.r, _refHero.c-1)){
						return (_direction);
					}
				}else{
					_roomAvail =-1*(_refHero.x-this.x-GameControl.CELL_WIDTH/2  -_refHero.getNextCell().x);
					if (_roomAvail == 0){
						dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
					}else if (_roomAvail+_dispX >= 0){
						this.x+=_dispX;
						_refHero.goEast(this.x);
						_roomAvail+=_dispX;
						if (_roomAvail < 4){
							this.x -= _roomAvail;
							_refHero.goEast(this.x);
							_roomAvail = 0;
						}
						if (_roomAvail == 0){
							return (_direction);
						}
					}else {
						this.x -= _roomAvail;
						return (_direction);
					}
				}
			}else if (_dispY < 0){
				if (_direction == GameEngine.DOWN_ARROW || _direction == -1){
					if (checkCell(_refHero.r+1, _refHero.c)){
						_refHero.setNextCell(_cellMatrix[_refHero.r][_refHero.c-1]);
						this.y+=_dispY;
						_refHero.goSouth(this.y);
					}else{
						_roomAvail = (this.y) - (-1*_refHero.getCellY() + _refHero.y - GameControl.CELL_HEIGHT/2);
						if (_roomAvail == 0){
							dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
						}else if (_roomAvail+_dispY >= 0){
							this.y+=_dispY;
							_refHero.goSouth(this.y);
							_roomAvail+=_dispY;
							if (_roomAvail < 4){
								this.y -= _roomAvail;
								_refHero.goSouth(this.y);
								_roomAvail = 0;
							}
							if (_roomAvail == 0){
								return (_direction);
							}
						}else {
							this.y -= _roomAvail;
							return (_direction);
						}
					}
				}else if (_direction == GameEngine.UP_ARROW){
					if (checkCell(_refHero.r-1, _refHero.c)){
						return (_direction);
					}
				}else{
					_roomAvail = (this.y) - (-1*_refHero.getCellY() + _refHero.y - GameControl.CELL_HEIGHT/2);
					if (_roomAvail == 0){
						dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
					}else if (_roomAvail+_dispY >= 0){
						this.y+=_dispY;
						_refHero.goSouth(this.y);
						_roomAvail+=_dispY;
						if (_roomAvail < 4){
							this.y -= _roomAvail;
							_refHero.goSouth(this.y);
							_roomAvail = 0;
						}
						if (_roomAvail == 0){
							return (_direction);
						}
					}else {
						this.y -= _roomAvail;
						return (_direction);
					}
				}
			}else if (_dispX > 0){
				if (_direction == GameEngine.LEFT_ARROW || _direction == -1){
					if (checkCell(_refHero.r, _refHero.c-1)){
						_refHero.setNextCell(_cellMatrix[_refHero.r-1][_refHero.c-2]);
						this.x+=_dispX;
						_refHero.goWest(this.x);
					}else{
						_roomAvail =_refHero.x-this.x-GameControl.CELL_WIDTH/2  -_refHero.getNextCell().x;
						if (_roomAvail == 0){
							dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
						}else if (_roomAvail-_dispX >= 0){
							this.x+=_dispX;
							_refHero.goWest(this.x);
							_roomAvail -=_dispX;
							if (_roomAvail < 4){
								this.x -= _roomAvail;
								_refHero.goWest(this.x);
								_roomAvail = 0;
							}
							if (_roomAvail == 0){
								return (_direction);
							}
						}else {
							this.x += _roomAvail;
							return (_direction);
						}
					}
				}else if (_direction == GameEngine.RIGHT_ARROW){
					if (checkCell(_refHero.r, _refHero.c+1)){
						return (_direction);
					}
				}else{
					_roomAvail =_refHero.x-this.x-GameControl.CELL_WIDTH/2  -_refHero.getNextCell().x;
					if (_roomAvail == 0){
						dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
					}else if (_roomAvail-_dispX >= 0){
						this.x+=_dispX;
						_refHero.goWest(this.x);
						_roomAvail -=_dispX;
						if (_roomAvail < 4){
							this.x -= _roomAvail;
							_refHero.goWest(this.x);
							_roomAvail = 0;
						}
						if (_roomAvail == 0){
							return (_direction);
						}
					}else {
						this.x += _roomAvail;
						return (_direction);
					}
				}
			}else if (_dispY > 0){
				if (_direction == GameEngine.UP_ARROW || _direction == -1){
					if (checkCell(_refHero.r-1, _refHero.c)){
						_refHero.setNextCell(_cellMatrix[_refHero.r-2][_refHero.c-1]);
						this.y+=_dispY;
						_refHero.goNorth(this.y);
					}else{
						_roomAvail = _refHero.y-this.y-GameControl.CELL_HEIGHT/2  -_refHero.getNextCell().y;
						if (_roomAvail == 0){
							dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
						}else if (_roomAvail -_dispY >= 0){
							this.y +=_dispY;
							_refHero.goNorth(this.y);
							_roomAvail -=_dispY;
							if (_roomAvail < 4){
								this.y += _roomAvail;
								_refHero.goNorth(this.y);
								_roomAvail = 0;
							}
							if (_roomAvail == 0){
								return (_direction);
							}
						}else {
							this.y += _roomAvail;
							return (_direction);
						}
					}
				}else if (_direction == GameEngine.DOWN_ARROW){
					if (checkCell(_refHero.r+1, _refHero.c)){
						return (_direction);
					}
				}else{
					_roomAvail = _refHero.y-this.y-GameControl.CELL_HEIGHT/2  -_refHero.getNextCell().y;
					if (_roomAvail == 0){
						dispatchEvent(new GameEvent(GameEvent.HIT_WALL));
					}else if (_roomAvail -_dispY >= 0){
						this.y +=_dispY;
						_refHero.goNorth(this.y);
						_roomAvail -=_dispY;
						if (_roomAvail < 4){
							this.y += _roomAvail;
							_refHero.goNorth(this.y);
							_roomAvail = 0;
						}
						if (_roomAvail == 0){
							return (_direction);
						}
					}else {
						this.y += _roomAvail;
						return (_direction);
					}
				}
			}
			return (-2);
		}
		
		
		private function shiftEast(_roomAvail:Number):void{
		}
		
		private function updateEnemyPositions(_dispX:Number, _dispY:Number):void{
			for (var i:int=0; i<_enemyList.length; i++){
				_enemyList[i].updatePosition();
			}
		}
		
		private function onKeyPickup(e:GameEvent):void{
			var _currCell:LevelCell = LevelCell(e._data);
			var _key:ZoneKey = _currCell.getKey();
			var _keyValue:int = GameControl.BASE_KEY_VALUE*GameControl._multiplier;
			GameControl._multiplier++;
			GameControl._keysCollected++;
			_currCell.setKey(false);
			_key.pickup(_keyValue);
			if (GameControl._keysCollected == GameControl.TOTAL_KEYS){
				_secureOpen = true;
				_secureZone.gotoAndStop("Open");
				dispatchEvent(new GameEvent(GameEvent.GOT_ALL_KEYS));
			}
			dispatchEvent(new GameEvent(GameEvent.GOT_KEY, _key)); 
		}
		
		private function onKeyAnimDone(e:GameEvent):void{
			ZoneKey(e._data).visible = false;
		}
		
		private function onSetEmp(e:GameEvent):void{
			var _currCell:LevelCell = LevelCell(e._data);
			var _emp:EMP = new EMP();
			_emp.setCell (_currCell);
			_emp.x = _currCell.x;
			_emp.y = _currCell.y;
			_empSnd.play();
			addChildAt(_emp, 2);
			_emp.play();
			_empList.push(_emp);
			TweenMax.to(_emp, GameControl.EMP_TIME, {onComplete:onEMPDone, onCompleteParams:[_emp]});
		}
		
		private function onEMPDone(_refClip:EMP):void{
			var _currCell:LevelCell = _refClip.getCell();
			if (_currCell != null){
				if (_currCell.getEmp() == _refClip){
					_currCell.clearEmp();
				}
			}
			_refClip.clearCell();
			removeChild(_refClip);
			for (var i:int=0; i<_empList.length; i++){
				if (_empList[i] == _refClip){
					_refClip.destroy();
					_empList[i] = null;
					_empList.splice(i,1);
				}
			}
		}

	}// Class
}// Package