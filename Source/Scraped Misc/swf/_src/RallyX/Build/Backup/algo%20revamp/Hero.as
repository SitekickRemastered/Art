package classes.game {
	
	import flash.display.MovieClip;
	import classes.game.LevelCell;
	import classes.control.GameControl;
	import classes.events.GameEvent;
	
	public class Hero extends MovieClip{
		
		private var _currCell:LevelCell;
		private var _nextCell:LevelCell;
		private var _empActive:Boolean;
		private var _heroClip:MovieClip;
		
		public function Hero() {
			init()
			faceEast();
			_empActive = false;
		
		}
		
		// Public Methods
		public function init():void{
			if (GameControl._gameLevel < 3){
				_heroClip = this.frantic;
				this.jinx.visible = false;
			}else{
				_heroClip = this.jinx;
				this.frantic.visible = false;
			}
			_heroClip.visible = true;
		}
		
		public function setCell(_refCell:LevelCell):void{
			_currCell = _refCell;
		}
		
		public function getCell():LevelCell{
			return (_currCell);
		}
		
		public function getNextCell():LevelCell{
			return (_nextCell);
		}
		
		public function setNextCell(_refCell:LevelCell):void{
			_nextCell = _refCell;
		}
		
		public function setEmp(_state:Boolean):void{
			_empActive = _state;
		}
		
		public function goEast(_mapX:Number):void{
			_mapX = (-1*_mapX)+this.x-GameControl.CELL_WIDTH/2;
			if (_currCell.hasEnemy){
				dispatchEvent(new GameEvent(GameEvent.LOSE_LIFE));
			}
			if (_nextCell != _currCell){
				if (_mapX > _nextCell.x){
					moveToNextCell();
				}
			}
		}
		
		public function goWest(_mapX:Number):void{
			_mapX = (-1*_mapX)+this.x-GameControl.CELL_WIDTH/2;
			if (_currCell.hasEnemy){
				dispatchEvent(new GameEvent(GameEvent.LOSE_LIFE));
			}
			if (_nextCell != _currCell){
				if (_mapX < _nextCell.x+GameControl.CELL_WIDTH){
					moveToNextCell();
				}
			}
		}
		
		public function goSouth(_mapY:Number):void{
			_mapY-=this.y-GameControl.CELL_HEIGHT/2;
			if (_currCell.hasEnemy){
				dispatchEvent(new GameEvent(GameEvent.LOSE_LIFE));
			}
			if ((_mapY < -1*(_nextCell.y)+GameControl.CELL_HEIGHT) && (_mapY >= -1*(_nextCell.y))){
				moveToNextCell();
			}
		}
		
		public function goNorth(_mapY:Number):void{
			_mapY = (-1*_mapY)+this.y-GameControl.CELL_HEIGHT/2;
			if (_currCell.hasEnemy){
				dispatchEvent(new GameEvent(GameEvent.LOSE_LIFE));
			}
			if (_nextCell != _currCell){
				if (_mapY < _nextCell.y+GameControl.CELL_HEIGHT){
					moveToNextCell();
				}
			}
		}
		
		public function getCellX():Number {
			return (_currCell.x);
		}
		
		public function getCellY():Number{
			return (_currCell.y);
		}
		
		public function faceEast():void{
			_heroClip.gotoAndStop("east");
		}
										
		public function faceWest():void{
			_heroClip.gotoAndStop("west");
		}
		
		public function faceNorth():void{
			_heroClip.gotoAndStop("north");
		}
		
		public function faceSouth():void{
			_heroClip.gotoAndStop("south");
		}
		
		// Getters
		public function get r():int{
			return (_currCell.r);
		}
		
		public function get c():int{
			return (_currCell.c);
		}
		
		public function get empActive():Boolean{
			return (_empActive);
		}
		
		// Private Methods 
		private function moveToNextCell():void{
			_currCell = _nextCell;
			//trace ("moved to: "+_nextCell.id);
			if (_empActive){
				dispatchEvent(new GameEvent(GameEvent.SET_EMP, _currCell));
			}
			if (_currCell.hasKey){
				dispatchEvent(new GameEvent(GameEvent.GOT_KEY, _currCell));
			}
		}

	}// Class
}// Package