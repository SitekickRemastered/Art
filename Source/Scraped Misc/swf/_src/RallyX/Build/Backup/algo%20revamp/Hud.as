package classes.game {
	
	import flash.display.Sprite;
	import flash.display.MovieClip;
	import classes.control.GameControl;
	import classes.game.Hero;
	import classes.game.Zomkick;
	import classes.game.ZoneKey;
	import classes.events.GameEvent;
	
	public class Hud extends Sprite{
		
		// Constants
		private const BLIP_MAP_X:Number = 12;
		private const BLIP_MAP_Y:Number = 110;
	
		// Private Properties
		private var _shiftX:Number;
		private var _shiftY:Number;
		private var _borderSpace:int;
		private var _heroBlip:Sprite;
		private var _keyBlips:Vector.<Sprite>;
		private var _enemyBlips:Vector.<Sprite>;
		private var _secureBlip:Sprite;
		
		private var _refHero:Hero;
		private var _refKeys:Vector.<ZoneKey>;
		private var _refEnemies:Vector.<Zomkick>;
		private var _prevScore:int;
		private var _empRate:Number;


		public function Hud() {
		}
		
		// Public Methods
		public function init(_rows:int, _cols:int, _border:int):void{
			_empRate = GameControl.GAS_RATE_EMP + GameControl.GASE_RATE_EMP_LEVEL_INC*GameControl._gameLevel;
			this.levelTxt.text = ""+GameControl._gameLevel;
			this.scoreTxt.text = ""+GameControl._score;
			this.keyCountTxt.text = ""+GameControl._keysCollected+" of "+GameControl.TOTAL_KEYS;
			_prevScore = GameControl._score;
			_borderSpace = _border;
			_shiftX  = 126/(_cols- (2*_border));
			_shiftY = 213/(_rows-(2*_border));
			for (var i:int = 1; i<= 5; i++){
				if (i<=GameControl._lives){
					this["rdf"+i].visible = true;
				}else{
					this["rdf"+i].visible = false; 
				}
			}
		}
		
		public function registerElements(_rHero:Hero, _rKeys:Vector.<ZoneKey>, _rEnemies:Vector.<Zomkick>, _sR:int, _sC:int){
			_refHero = _rHero;
			_refKeys = _rKeys;
			_refEnemies = _rEnemies;
			
			_secureBlip = new ExitBlip();
			_secureBlip.x = BLIP_MAP_X + (_sC-1 - _borderSpace)*_shiftX;
			_secureBlip.y = BLIP_MAP_Y + (_sR-1 - _borderSpace)*_shiftY;
			
			_heroBlip = new FranticBlip();
			_heroBlip.x = BLIP_MAP_X + (_refHero.c-1 - _borderSpace)*_shiftX;
			_heroBlip.y = BLIP_MAP_Y + (_refHero.r-1 - _borderSpace)*_shiftY;
			
			_enemyBlips = new Vector.<Sprite>();
			for (i=0; i<_rEnemies.length; i++){
				var _eblip:Sprite = new EnemyBlip();
				_eblip.x =  BLIP_MAP_X + (_rEnemies[i].c-1-_borderSpace)*_shiftX;
				_eblip.y =  BLIP_MAP_Y + (_rEnemies[i].r-1-_borderSpace)*_shiftY;
				addChild (_eblip);
				_enemyBlips.push(_eblip);
			}
			
			_keyBlips = new Vector.<Sprite>();
			for (var i:int=0; i<_rKeys.length; i++){
				var _blip:Sprite = new KeyBlip();
				_blip.x =  BLIP_MAP_X + (_rKeys[i].c-1-_borderSpace)*_shiftX;
				_blip.y =  BLIP_MAP_Y + (_rKeys[i].r-1-_borderSpace)*_shiftY;
				addChild (_blip);
				_keyBlips.push(_blip);
			}
			
			addChild (_secureBlip);
			addChild (_heroBlip);
		}
		
		public function clearElements():void{
			_refHero = null;
			_refKeys = null;
			removeChild (_secureBlip);
			_secureBlip = null;
			removeChild (_heroBlip);
			_heroBlip = null;
			while(_keyBlips.length != 0){
				removeChild (_keyBlips[0]);
				_keyBlips[0] = null;
				_keyBlips.splice(0, 1);
			}
			_keyBlips = null;
		}
		
		public function updateMap():void{
			_heroBlip.x = BLIP_MAP_X + (_refHero.c-1 - _borderSpace)*_shiftX;
			_heroBlip.y = BLIP_MAP_Y+ (_refHero.r-1 - _borderSpace)*_shiftY;
			for (var i:int=0; i<_refEnemies.length; i++){
				var _eblip:Sprite =_enemyBlips[i];
				_eblip.x =  BLIP_MAP_X + (_refEnemies[i].c-1-_borderSpace)*_shiftX;
				_eblip.y =  BLIP_MAP_Y + (_refEnemies[i].r-1-_borderSpace)*_shiftY;
			}
		}
		
		public function updateScore(_refKey:ZoneKey):void{
			GameControl._score += _refKey.scoreValue;
			this.keyCountTxt.text = ""+GameControl._keysCollected+" of "+GameControl.TOTAL_KEYS;
			var _breakValue:int = GameControl.BONUS_LIFE_BASE + GameControl.BONUS_LIFE_INCREMENT*GameControl._lifeIncrement;
			
			for (var i:int=0; i<_refKeys.length; i++){
				if (_refKey == _refKeys[i]){
					_keyBlips[i].visible = false;
					break;
				}
			}
			
			if ((GameControl._score > _breakValue) && _prevScore < _breakValue){
				if (GameControl._lives < GameControl.MAX_LIVES){
					GameControl._lives++;
					GameControl._lifeIncrement++;
					updateLife();
					dispatchEvent(new GameEvent(GameEvent.LIFE_UP));
				}
			}
			this.scoreTxt.text = ""+GameControl._score;
		}
		
		public function updateGas(_empState:Boolean):void{
			if (_empState){
				GameControl._empLevel-= _empRate;
			}else{
				GameControl._empLevel-= GameControl.GAS_RATE;
			}
			if (GameControl._empLevel<=0){
				dispatchEvent(new GameEvent(GameEvent.LOSE_LIFE));
			}
			this.empMeter.empBar.x = GameControl._empLevel - 100;
		}
		
		public function resetLifeVariables():void{
			this.empMeter.empBar.x = 0;
		}
		
		public function updateLife():void{
			for (var i:int = 1; i<=GameControl.MAX_LIVES ; i++)
			if (GameControl._lives >= i){
				this["rdf"+i].visible = true;
			}else{
				this["rdf"+i].visible = false;
			}
		}

	}// Class
}// Package