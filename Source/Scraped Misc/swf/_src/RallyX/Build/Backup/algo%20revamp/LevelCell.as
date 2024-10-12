package classes.game {
	
	import flash.display.MovieClip;
	import classes.game.ZoneKey;
	import classes.game.EMP;
	import classes.game.Zomkick;
	
	public class LevelCell {
		
		// Private Properties
		private var _cellID:String;
		private var _cellR:int;
		private var _cellC:int;
		private var _cellType:Boolean;
		private var _hasKey:Boolean;
		private var _hasEmp:Boolean;
		private var _hasEnemy:Boolean;
		private var _rX:Number;
		private var _rY:Number;
		private var _refKey:ZoneKey;
		private var _refEmp:EMP;
		private var _refEnemy:Zomkick;
		
		// Constructor
		public function LevelCell() {
			_cellID = "na";
			_cellType = false;
			_hasKey = false;
			_hasEmp = false;
			_hasEnemy = false;
			_cellR = -1;
			_cellC = -1;
			_rX = 0;
			_rY = 0;
		}
		
		// Publilc Methods
		public function init(_id:String, _r:int, _c:int):void{
			_cellID = _id;
			_cellR = _r;
			_cellC = _c;
		}
		
		public function destroy():void{
			_refKey = null;
			_refEmp = null;
			_refEnemy = null;
			_hasEmp = false;
			_hasKey = false;
			_hasEnemy = false;
		}
		
		public function setEnemy(_rEnemy:Zomkick):void{
			_refEnemy = _rEnemy;
			_hasEnemy = true;
		}
		
		public function clearEnemy():void{
			if (_hasEnemy){
				_hasEnemy = false;
				_refEnemy = null;
			}
		}
		
		public function setEmp(_refClip:EMP):void{
			_hasEmp = true;
			_refEmp = _refClip;
		}
		
		public function clearEmp():void{
			if (_hasEmp){
				_hasEmp = false;
				_refEmp = null;
			}
		}
		
		public function setKey(_state:Boolean, _keyClip:ZoneKey = null):void{ 
			_hasKey = _state;
			_refKey = _keyClip;
		}
		
		public function getKey():ZoneKey{
			return (_refKey);
		}
		
		public function getEmp():MovieClip{
			return (_refEmp);
		}
		
		// getters
		public function get x():Number{
			return (_rX);
		}
		
		public function get y():Number{
			return (_rY);
		}
		
		public function get hasKey():Boolean{
			return (_hasKey);
		}
		
		public function get hasEmp():Boolean{
			return (_hasEmp);
		}
		
		public function get hasEnemy():Boolean{
			return (_hasEnemy);
		}
		
		public function get id():String{
			return (_cellID);
		}
		
		public function get r():int{
			return (_cellR);
		}
		
		public function get c():int{
			return (_cellC);
		}
		
		public function get type():Boolean{
			return (_cellType);
		}
		
		// Setters
		public function set x(_n:Number):void{
			_rX = _n;
		}
		
		public function set y(_n:Number):void{
			_rY = _n;
		}
		
		public function set r(_rID:int):void{
			_cellR = _rID;
		}
		
		public function set c(_cID):void{
			_cellC = _cID;
		}
		
		public function set type(_t:Boolean):void{
			_cellType = _t;
		}
		

	}// Class
}// Package