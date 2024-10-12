package classes.control {
	
	public class GameControl {
		
		// Constants
		public static const CELL_WIDTH:Number = 50;
		public static const CELL_HEIGHT:Number = 50;
		public static const SPEEDX:Number = 10;
		public static const SPEEDY:Number = 10;
		public static const TOTAL_KEYS:int = 10;
		public static const GAS_RATE:Number = 0.3;
		public static const GAS_RATE_EMP:Number = 0.6;
		public static const BASE_KEY_VALUE:int = 100;
		public static const EMP_TIME:Number = 1.0;
		public static const BONUS_LIFE_BASE:int = 20000;
		public static const BONUS_LIFE_INCREMENT:int = 10000;
		public static const MAX_LIVES:int = 5;

		// Game Variables
		public static var _gameLevel:int = 1;
		public static var _score:int = 0;
		public static var _keysCollected:int = 0;
		public static var _multiplier:int = 1;
		public static var _lifeIncrement:int = 0;
		public static var _lives:int = 5;
		
		public static function resetGameVariables():void{
			_gameLevel = 1;
			_score = 0;
			_keysCollected = 0;
			_lifeIncrement = 0;
			_multiplier = 1;
			_lives = 5;
		}
		
		public static function resetLevelVariables():void{
			_keysCollected = 0;
		}
		
		public static function resetLifeVariables():void{
			_multiplier = 1;
		}

		
	}// Class
}// Package