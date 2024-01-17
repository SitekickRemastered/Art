using Sitekick;
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

[InitializeOnLoad]
public static class ChipPrefabStage
{
	private static Dictionary<PrefabStage, EditorStage> editorStages = new Dictionary<PrefabStage, EditorStage>();

	static ChipPrefabStage()
	{
		AssemblyReloadEvents.beforeAssemblyReload += AssemblyReloadEvents_beforeAssemblyReload;

		PrefabStage.prefabStageOpened += PrefabStage_prefabStageOpened;
		PrefabStage.prefabStageClosing += PrefabStage_prefabStageClosing;

		var currentPrefabStage = PrefabStageUtility.GetCurrentPrefabStage();
		if ( currentPrefabStage != null )
			PrefabStage_prefabStageOpened( currentPrefabStage );
	}

	private static void AssemblyReloadEvents_beforeAssemblyReload()
	{
		var stages = editorStages.Keys.ToArray();
		foreach ( var stage in stages )
			PrefabStage_prefabStageClosing( stage );
	}

	private static void PrefabStage_prefabStageOpened( PrefabStage stage )
	{
		if ( editorStages.TryGetValue( stage, out var currentStage ) && currentStage != null )
			currentStage.Destroy();

		var editorStage = new EditorStage( stage );
		editorStages[stage] = editorStage;
	}

	private static void PrefabStage_prefabStageClosing( PrefabStage stage )
	{
		if ( editorStages.TryGetValue( stage, out var editorStage ) )
		{
			editorStage.Destroy();
			editorStages.Remove( stage );
		}
	}

	public class EditorStage
	{
		private static GameObject sitekickPrefab = null;
		private static GameObject SitekickPrefab
		{
			get
			{
				if ( sitekickPrefab == null )
					sitekickPrefab = AssetDatabase.LoadAssetAtPath<GameObject>( AssetDatabase.GUIDToAssetPath( "921ac30dc75efae4ab85e4cd6c807c70" ) );
				return sitekickPrefab;
			}
		}

		protected EditorSitekick sitekickInstance = null;
		protected SortingGroup sitekickSortingGroup = null;

		protected PrefabStage currentStage = null;
		protected ChipData currentChip = null;
		protected ChipEffect currentEffect = null;

		protected bool showSitekick
		{
			get => EditorPrefs.GetBool( nameof( showSitekick ), true );
			set => EditorPrefs.SetBool( nameof( showSitekick ), value );
		}

		protected float sitekickAlpha
		{
			get => EditorPrefs.GetFloat( nameof( sitekickAlpha ), 1f );
			set => EditorPrefs.SetFloat( nameof( sitekickAlpha ), value );
		}

		private Color? _sitekickColor = null;
		protected Color sitekickColor
		{
			get
			{
				if ( !_sitekickColor.HasValue )
				{
					var colorStr = "#FFCC00";

					if ( EditorPrefs.HasKey( nameof( sitekickColor ) ) )
					{
						colorStr = EditorPrefs.GetString( nameof( sitekickColor ), colorStr );
						if ( !colorStr.StartsWith( '#' ) )
							colorStr = $"#{colorStr}";
					}

					if ( ColorUtility.TryParseHtmlString( colorStr, out var col ) )
						_sitekickColor = col;
				}

				return _sitekickColor.HasValue ? _sitekickColor.Value : Color.white;
			}

			set
			{
				if ( !_sitekickColor.HasValue || _sitekickColor.Value != value )
				{
					_sitekickColor = value;
					EditorPrefs.SetString( nameof( sitekickColor ), ColorUtility.ToHtmlStringRGB( value ) );
				}
			}
		}

		public EditorStage( PrefabStage prefabStage )
		{
			currentStage = prefabStage;

			try
			{
				if ( !prefabStage.assetPath.Contains( "Assets/Chips/" ) )
					return;

				if ( ChipData.TryParseChipName( currentStage.prefabContentsRoot.name, out var chipID ) )
				{
					currentChip = AssetDatabase.FindAssets( $"t:ChipData {chipID}" )
						.Select( x => AssetDatabase.LoadAssetAtPath<ChipData>( AssetDatabase.GUIDToAssetPath( x ) ) )
						.FirstOrDefault( x => x.id == chipID );
				}

				currentEffect = prefabStage.prefabContentsRoot.GetComponent<ChipEffect>();

				if ( SitekickPrefab != null )
				{
					sitekickInstance = GameObject.Instantiate( SitekickPrefab ).GetComponent<EditorSitekick>();
					sitekickInstance.gameObject.hideFlags = HideFlags.DontSave;

					SceneManager.MoveGameObjectToScene( sitekickInstance.gameObject, prefabStage.scene );

					sitekickSortingGroup = sitekickInstance.GetComponent<SortingGroup>();
					if ( sitekickSortingGroup == null )
						sitekickSortingGroup = sitekickInstance.gameObject.AddComponent<SortingGroup>();

					sitekickSortingGroup.sortingLayerID = SortingLayer.NameToID( "Default" );
					sitekickSortingGroup.sortingOrder = 0;

					UpdateSitekick();

					SceneView.duringSceneGui -= SceneView_duringSceneGui;
					SceneView.duringSceneGui += SceneView_duringSceneGui;

					EditorApplication.delayCall += () =>
					{
						var camera = SceneView.GetAllSceneCameras().FirstOrDefault();
						if ( camera != null )
							SceneView.lastActiveSceneView.Frame( new Bounds( Vector3.zero, new Vector3( 5, 5, 0 ) ) );
					};
				}
			}
			catch ( Exception e )
			{
				Debug.LogException( e );

				Destroy();
			}
		}

		~EditorStage()
		{
			Destroy();
		}

		public void Destroy()
		{
			if ( sitekickInstance != null )
			{
				GameObject.DestroyImmediate( sitekickInstance.gameObject );
				sitekickInstance = null;
			}

			SceneView.duringSceneGui -= SceneView_duringSceneGui;

			currentStage = null;
			currentChip = null;
		}

		protected void SceneView_duringSceneGui( SceneView sceneView )
		{
			Rect windowRect = new Rect( 5, 50, 120, 50 );
			Handles.BeginGUI();
			{
				windowRect = GUILayout.Window( 0, windowRect, DrawSitekickWindow, "Sitekick" );
			}
			Handles.EndGUI();

			//Handles.RectangleHandleCap( 0, Vector3.zero, Quaternion.identity, ( 1024f / 100f ) / 2f, EventType.Repaint );
		}

		protected void DrawSitekickWindow( int windowID )
		{
			showSitekick = GUILayout.Toggle( showSitekick, "Visible" );

			if ( showSitekick )
			{
				using ( new GUILayout.HorizontalScope() )
				{
					GUILayout.Label( "Alpha", GUILayout.Width( 40f ) );

					sitekickAlpha = GUILayout.HorizontalSlider( sitekickAlpha, 0f, 1f );

					GUILayout.Space( 5f );
				}

				using ( new GUILayout.HorizontalScope() )
				{
					GUILayout.Label( "Color", GUILayout.Width( 40f ) );

					sitekickColor = EditorGUILayout.ColorField( sitekickColor );

					GUILayout.Space( 5f );
				}
			}

			UpdateSitekick();
		}

		protected void UpdateSitekick()
		{
			if ( sitekickInstance == null )
				return;

			sitekickInstance.gameObject.SetActive( showSitekick );

			sitekickInstance.SetAlpha( sitekickAlpha );

			sitekickInstance.SetColor( sitekickColor );

			if ( currentEffect != null )
				currentEffect.ApplyColor( sitekickColor );

			if ( currentChip != null )
			{
				if ( currentChip.effectType == ChipData.EffectType.Default )
					sitekickInstance.SetEffectFlags( currentChip.effectFlags );

				else if ( currentChip.effectType == ChipData.EffectType.Transformation )
					sitekickInstance.SetEffectFlags( ChipData.EffectFlags.HideAll );

				else if ( currentChip.effectType == ChipData.EffectType.Background || currentChip.effectType == ChipData.EffectType.Foreground )
					sitekickInstance.SetEffectFlags( ChipData.EffectFlags.None );

				if ( currentChip.effectLayer == ChipData.EffectLayer.InFront || currentChip.effectLayer == ChipData.EffectLayer.Foreground )
					sitekickSortingGroup.sortingOrder = -100;

				else if ( currentChip.effectLayer == ChipData.EffectLayer.Behind || currentChip.effectLayer == ChipData.EffectLayer.Background )
					sitekickSortingGroup.sortingOrder = 100;

				else
					sitekickSortingGroup.sortingOrder = 0;
			}
		}
	}
}
