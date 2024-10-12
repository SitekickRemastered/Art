package classes.screens {
	
	import classes.screens.ScreenBase;
	import classes.control.GameControl;
	import classes.events.ScreenEvent;
	import flash.events.MouseEvent;
	import flash.display.MovieClip;
	
	public class AnimationScreen extends ScreenBase {
		
		
		// Private Properties
		private var _currAnimation:MovieClip;
		private var _hasListener:Boolean;

		// Constructor
		public function AnimationScreen() {
		}
		
		// Public Methods
		override public function init():void{
			if (_currAnimation!= null){
				_currAnimation.stop();
				removeChild(_currAnimation);
				if (_hasListener){
					_currAnimation.refParent = null;
					_currAnimation.skipBtn.addEventListener(MouseEvent.CLICK, onEndAnimation);
				}
				_currAnimation = null;
			}
			if (GameControl._gameLevel == 1){
				_currAnimation = new Animation1();
			}else if (GameControl._gameLevel == 2){
				_currAnimation = new Animation1();
			}else if (GameControl._gameLevel == 3){
				_currAnimation = new Animation1();
			}
			
			_currAnimation.gotoAndStop(1);
			_currAnimation.refParent = this;
			_currAnimation.skipBtn.addEventListener(MouseEvent.CLICK, onEndAnimation);
			_hasListener = true;
			addChild(_currAnimation);
			dispatchEvent(new ScreenEvent(ScreenEvent.INITIALIZED));
		}
		
		override public function startShow():void{
			_currAnimation.play();
		}
		
		// Internal Public Methods
		public function onEndAnimation(e:MouseEvent = null):void{
			_currAnimation.stop();
			if (_hasListener){
				_currAnimation.skipBtn.removeEventListener(MouseEvent.CLICK, onEndAnimation);
				_hasListener = false;				
			}
			dispatchEvent(new ScreenEvent(ScreenEvent.ANIMATION_COMPLETE));
		}
		
	}// Class
}// Package