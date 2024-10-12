package classes.game {
	
	import flash.display.MovieClip;
	import classes.game.LevelCell;
	import classes.game.Hero;
	import classes.control.GameControl;
	
	public class Zomkick extends MovieClip{
		
		private var _refMatrix:Vector.<Vector.<LevelCell>>;
		private var _refHero:Hero;
		private var _currCell:LevelCell;
		private var _nextCell:LevelCell;
		private var _prevCell:LevelCell;
		private var _moveAlgorithm:Function;
		private var _speedX:Number;
		private var _speedY:Number;
		private var _feignR:int;
		private var _feignC:int;
		private var _zomType:int;
		private var _confused:Boolean;
		private var _iniCell:LevelCell;

		public function Zomkick(_targetR:int, _targetC:int) {
			faceNorth();
			_confused = false;
			_feignR = _targetR;
			_feignC = _targetC;
			_zomType = Math.round(Math.random()*2);
			trace ("zomtype : "+_zomType);
			switch(_zomType){
				case (0):
					_moveAlgorithm = algorithm1;
					break;
				case (1):
					_moveAlgorithm = algorithm2;
					break;
				case (2):
					_moveAlgorithm = algorithm3;
					break;
			}
		}
		
		// Public Methods
		public function destroy():void{
			_currCell.clearEnemy();
			_currCell = null;
			_nextCell = null;
			_prevCell = null;
			_iniCell = null;
			_moveAlgorithm = null;
			_refHero = null;
			_refMatrix = null;
			this.gotoAndStop(1);
			while (this.numChildren!= 0){
				removeChildAt(0);
			}
		}
		
		public function setCell(_refCell:LevelCell):void{
			_currCell = _refCell;
			_nextCell = _refCell;
			_prevCell = _refCell;
			_iniCell = _refCell;
			this.x = _currCell.x;
			this.y = _currCell.y;
		}
		
		public function resetPosition():void{
			_currCell.clearEnemy();
			setCell(_iniCell);
			faceNorth();
			_confused = false;
		}
		
		public function setMatrix(_rMatrix:Vector.<Vector.<LevelCell>>):void{
			_refMatrix = _rMatrix;
		}
		
		public function registerHero(_rHero:Hero):void{
			_refHero = _rHero;
		}
		
		public function updatePosition():void{
			if (_currCell == _nextCell){
				_moveAlgorithm();
			}else{
				if (_currCell.hasEmp){
					if (!_confused){
						confused();
					}
				}else{
					var _added:Boolean = false;
					if (_currCell.c < _nextCell.c){
						if (this.x+_speedX >= _nextCell.x){
							_added = this.shiftCell();
						}
					}else if (_currCell.c > _nextCell.c){
						if (this.x+_speedX <= _nextCell.x){
							_added = this.shiftCell();
						}
					}else if (_currCell.r < _nextCell.r){
						if (this.y+_speedY >= _nextCell.y){
							_added = this.shiftCell();
						}
					}else if (_currCell.r > _nextCell.r){
						if (this.y+_speedY <= _nextCell.y){
							_added = this.shiftCell();
						}
					}
					if (!_added){
						this.x += _speedX;
						this.y += _speedY;
					}
				}
			}
		}
		
		public function faceEast():void{
			_confused = false;
			this.gotoAndStop("east");
		}
										
		public function faceWest():void{
			_confused = false;
			this.gotoAndStop("west");
		}
		
		public function faceNorth():void{
			_confused = false;
			this.gotoAndStop("north");
		}
		
		public function faceSouth():void{
			_confused = false;
			this.gotoAndStop("south");
		}
		
		public function confused():void{
			_confused = true;
			this.gotoAndStop("confused");
		}
		
		// getters
		public function get r():int{
			return (_currCell.r);
		}
		
		public function get c():int{
			return (_currCell.c);
		}
		
		// Private Methods
		private function algorithm1():void{
			setNetCell(_refHero.getCell());
			setMovement();
		}
		
		private function algorithm2():void{
			setNetCell(_refHero.getNextCell());
			setMovement();
		}
		
		private function algorithm3():void{
			if (compareDistance(_currCell.r, _currCell.c, _refHero.getCell(), 3000) >=8){
				algorithm1();
			}else{
				setNetCell(_refMatrix[_feignR-1][_feignC-1]);
				setMovement();
			}
		}
		
		private function compareDistance(_compR:int, _compC:int,  _compCell:LevelCell, _dist:int):int{
			if (checkCell(_compR, _compC)){
				var _nDist:int = Math.abs(_compR - _compCell.r) + Math.abs(_compC - _compCell.c);
				if (_nDist < _dist){
					_nextCell = _refMatrix[_compR-1][_compC-1];
					return (_nDist);
				}
			}
			return (_dist);
		}
		
		private function checkCell(_r:int, _c:int):Boolean {
			if ((_r-1 < _refMatrix.length) && (_r-1>-1)){
				if ((_c-1 < _refMatrix[0].length) && (_c-1>-1)){
					return (_refMatrix[_r-1][_c-1].type);
				}
			}
			return (false);
		}
		
		private function compareCell(_cell:LevelCell, _r:int, _c:int):Boolean{
			if ((_cell.r == _r) && (_cell.c == _c)){
				return (true);
			}
			return (false);
		}
		
		private function setNetCell(_checkCell:LevelCell):void{
			var _dist:int = 3000;
			var _r:int = _currCell.r-1;
			var _c:int = _currCell.c;
			if (!compareCell(_prevCell, _r, _c)){
				_dist = compareDistance(_r, _c, _checkCell, _dist);
			}
			_r = _currCell.r+1;
			if (!compareCell(_prevCell, _r, _c)){
				_dist = compareDistance(_r, _c, _checkCell,_dist);
			}
			_r = _currCell.r;
			_c = _currCell.c-1;
			if (!compareCell(_prevCell, _r, _c)){
				_dist = compareDistance(_r, _c, _checkCell,_dist);
			}
			_c = _currCell.c+1;
			if (!compareCell(_prevCell, _r, _c)){
				_dist = compareDistance(_r, _c, _checkCell,_dist);
			}
		}
		
		private function setMovement():void{
			if (_nextCell.r < _currCell.r){
				faceNorth();
				_speedY = -1*GameControl.SPEEDY;
				_speedX = 0;
			}else if (_nextCell.r > _currCell.r){
				faceSouth();
				_speedY = GameControl.SPEEDY;
				_speedX = 0;
			}else if (_nextCell.c < _currCell.c){
				faceWest();
				_speedX = -GameControl.SPEEDX;
				_speedY = 0;
			}else{
				faceEast();
				_speedX = GameControl.SPEEDX;
				_speedY = 0;
			}
		}
		
		private function shiftCell():Boolean{
			this.x = _nextCell.x;
			_prevCell = _currCell;
			_currCell = _nextCell;
			_prevCell.clearEnemy();
			_currCell.setEnemy(this);
			if (_currCell.hasEmp){
				confused();
			}
			return (true);
		}

	}// Class
}// Package