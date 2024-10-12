package classes.game {
	
	import flash.display.MovieClip;
	import classes.game.LevelCell;
	
	public class EMP extends MovieClip{

		private var _currCell:LevelCell;

		public function EMP() {
			stop();
		}
		
		public function destroy():void{
			this.stop();
			if (_currCell != null){
				if (_currCell.getEmp() == this){
					_currCell.clearEmp();
				}
			}
			_currCell = null;
		}
		
		public function setCell(_refCell:LevelCell):void{
			_currCell = _refCell;
			_currCell.setEmp(this);
		}
		
		public function clearCell():void{
			if (_currCell.getEmp() == this){
				_currCell.clearEmp();
			}
			_currCell = null;
		}
		
		public function getCell():LevelCell{
			return (_currCell);
		}

	}// Class
}// Package