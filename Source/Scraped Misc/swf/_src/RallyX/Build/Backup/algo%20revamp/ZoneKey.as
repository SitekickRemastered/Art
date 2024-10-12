package classes.game {
	
	import classes.game.LevelCell;
	import flash.display.MovieClip;
	import classes.events.GameEvent;
	
	public class ZoneKey extends MovieClip{

		// Private Properties
		private var _currCell:LevelCell;
		private var _isActive:Boolean;
		private var _scoreValue:int;

		public function ZoneKey() {
			this.gotoAndStop(1);
			_isActive = true;
			_scoreValue = 0;
		}

		// Public Methods
		public function destroy():void{
			this.stop();
			_currCell = null;
			while(this.numChildren!=0){
				removeChildAt(0);
			}
		}
		
		public function setCell(_refCell:LevelCell):void{
			_currCell = _refCell;
		}
		
		public function pickup(_value:int):void{
			_scoreValue = _value;
			this.scoreClip.scoreTxt.text = ""+_value;
			_isActive = false;
			this.gotoAndPlay("Pickup");
		}
		
		public function get r():int{
			return (_currCell.r);
		}
		
		public function get c():int{
			return (_currCell.c);
		}
		
		public function get isActive():Boolean{
			return (_isActive);
		}
		
		public function get scoreValue():int{
			return (_scoreValue);
		}
		
		// Internal Public Methods
		public function keyDone():void{
			stop();
			dispatchEvent(new GameEvent(GameEvent.KEY_ANIM_DONE, this));
		}
		

	}// Class
}// Package